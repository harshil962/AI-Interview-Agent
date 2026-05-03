import os
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from database import delete_interview_by_id
from ai_helper import generate_ai_question, evaluate_answer
import requests
from datetime import datetime

from database import (
    init_db,
    create_user,
    get_user_by_email,
    get_user_by_id,
    update_preferred_topic,
    save_interview,
    get_user_interviews,
    get_dashboard_stats,
    delete_interview_by_id
)

url = os.getenv("N8N_WEBHOOK_URL")

app = Flask(__name__)
app.secret_key = "super-secret-key-change-this"

init_db()



def send_result_to_n8n(name, email, topic, score, question, answer, feedback):
    url = "http://localhost:5678/webhook/interview-result"

    data = {
        "name": name,
        "email": email,
        "topic": topic,
        "score": score,
        "question": question,
        "answer": answer,
        "feedback": feedback,
        "date": datetime.now().strftime("%Y-%m-%d")
    }

    try:
        response = requests.post(url, json=data, timeout=10)
        print("Sent to n8n:", response.status_code)
    except Exception as e:
        print("Error:", e)
        
def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please login first.", "warning")
            return redirect(url_for("login"))
        return func(*args, **kwargs)
    return wrapper


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not name or not email or not password or not confirm_password:
            flash("All fields are required.", "danger")
            return redirect(url_for("register"))

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("register"))

        existing_user = get_user_by_email(email)
        if existing_user:
            flash("Email already registered. Please login.", "warning")
            return redirect(url_for("login"))

        hashed_password = generate_password_hash(password)
        create_user(name, email, hashed_password)

        flash("Registration successful. Please login.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        user = get_user_by_email(email)

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            flash("Login successful.", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid email or password.", "danger")
            return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


@app.route("/dashboard")
@login_required
def dashboard():
    user = get_user_by_id(session["user_id"])
    stats = get_dashboard_stats(session["user_id"])
    interviews = get_user_interviews(session["user_id"])[:5]
    return render_template("dashboard.html", user=user, stats=stats, interviews=interviews)


@app.route("/start-interview", methods=["GET", "POST"])
@login_required
def start_interview():
    if request.method == "POST":
        topic = request.form.get("topic", "").strip()
        custom_topic = request.form.get("custom_topic", "").strip()
        difficulty = request.form.get("difficulty", "easy").strip()
        question_type = request.form.get("question_type", "theory").strip()

        final_topic = custom_topic if custom_topic else topic

        if not final_topic:
            flash("Please select or enter a topic.", "danger")
            return redirect(url_for("start_interview"))

        question = generate_ai_question(final_topic, difficulty, question_type)

        return render_template(
            "start_interview.html",
            selected_topic=final_topic,
            selected_difficulty=difficulty,
            selected_type=question_type,
            question=question
        )

    return render_template(
        "start_interview.html",
        selected_topic=None,
        selected_difficulty=None,
        selected_type=None,
        question=None
    )


@app.route("/submit-answer", methods=["POST"])
@login_required
def submit_answer():
    topic = request.form.get("topic")
    question = request.form.get("question")
    answer = request.form.get("answer", "").strip()
    question_type = request.form.get("question_type", "theory")

    print("TOPIC:", topic)
    print("QUESTION:", question)
    print("ANSWER:", answer)
    print("QUESTION TYPE:", question_type)

    result = evaluate_answer(question, answer, topic, question_type)

    save_interview(
        session["user_id"],
        topic,
        question,
        answer,
        result["feedback"],
        result["score"]
    )

    user = get_user_by_id(session["user_id"])

    print("SENDING TO N8N:", {
        "name": user["name"],
        "email": user["email"],
        "topic": topic,
        "score": result["score"],
        "question": question,
        "answer": answer
    })

    send_result_to_n8n(
        name=user["name"],
        email=user["email"],
        topic=topic,
        score=result["score"],
        question=question,
        answer=answer,
        feedback=result["feedback"]
    )

    return render_template(
        "result.html",
        topic=topic,
        question=question,
        answer=answer,
        feedback=result["feedback"],
        score=result["score"]
    )


@app.route("/history")
@login_required
def history():
    interviews = get_user_interviews(session["user_id"])
    return render_template("history.html", interviews=interviews)


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user = get_user_by_id(session["user_id"])

    if request.method == "POST":
        preferred_topic = request.form.get("preferred_topic")
        update_preferred_topic(session["user_id"], preferred_topic)
        flash("Profile updated successfully.", "success")
        return redirect(url_for("profile"))

    return render_template("profile.html", user=user)


@app.route("/api/reminder-webhook", methods=["POST"])
def reminder_webhook():
    """
    n8n can send data here.
    Example JSON:
    {
      "email": "student@gmail.com",
      "topic": "Python",
      "message": "Today's practice reminder"
    }
    """
    data = request.get_json(silent=True) or {}
    return jsonify({
        "status": "success",
        "received": data,
        "message": "Webhook received successfully."
    })

@app.route("/delete-interview/<int:interview_id>", methods=["POST"])
@login_required
def delete_interview(interview_id):
    delete_interview_by_id(interview_id, session["user_id"])
    flash("Interview deleted successfully!", "success")
    return redirect(url_for("history"))



if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
    
    

