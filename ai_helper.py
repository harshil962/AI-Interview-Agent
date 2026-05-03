import os
import re
from dotenv import load_dotenv
from google import genai
from tenacity import retry, stop_after_attempt, wait_exponential

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

client = genai.Client(api_key=API_KEY) if API_KEY else None


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=10)
)
def call_gemini(prompt):
    if not client:
        raise Exception("Gemini API key missing")

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt
    )

    text = (response.text or "").strip()

    if not text:
        raise Exception("Empty Gemini response")

    return text


def generate_ai_question(topic, difficulty="easy", question_type="theory"):
    fallback_questions = {
        "theory": f"What is {topic}? Explain with one simple example.",
        "coding": f"Write a simple Python program related to {topic}.",
        "mcq": f"""Question: What is the primary use of {topic}?
A) To manage database-related logic
B) To design frontend pages only
C) To run CSS files
D) To store images only""",
        "hr": "Tell me about yourself."
    }

    if question_type == "mcq":
        prompt = f"""
Generate exactly one MCQ interview question.

Topic: {topic}
Difficulty: {difficulty}

Strict format:
Question: <question>
A) <option>
B) <option>
C) <option>
D) <option>

Rules:
- Must include exactly 4 options
- Do not give answer
- Do not explain
- Suitable for fresher/student
"""
    else:
        prompt = f"""
Generate exactly one interview question.

Topic: {topic}
Difficulty: {difficulty}
Question Type: {question_type}

Rules:
- Return only one question
- No answer
- No explanation
- Suitable for student/fresher
"""

    try:
        text = call_gemini(prompt)
        return text
    except Exception as e:
        print("AI Question Error:", repr(e))
        return fallback_questions.get(question_type, f"What is {topic}?")


def evaluate_answer(question, answer, topic="General", question_type="theory"):
    answer = answer.strip()

    if not answer:
        return {
            "score": 0,
            "feedback": """Score: 0
Strengths:
- No answer written

Mistakes:
- Please attempt the answer

Better Answer:
Write a clear definition with one simple example."""
        }

    if question_type == "mcq":
        return evaluate_mcq_answer(answer)

    prompt = f"""
You are a strict but helpful interview evaluator.

Topic: {topic}
Question Type: {question_type}
Question: {question}
Candidate Answer: {answer}

Evaluate for fresher/student.

Return exactly this format:

Score: <0-10>
Strengths:
- ...
Mistakes:
- ...
Better Answer:
...
"""

    try:
        feedback = call_gemini(prompt)
        score = extract_score(feedback)

        return {
            "score": score,
            "feedback": feedback
        }

    except Exception as e:
        print("AI Evaluation Error:", repr(e))
        return rule_based_evaluation(answer)


def evaluate_mcq_answer(answer):
    answer = answer.strip().upper()

    if answer in ["A", "B", "C", "D"]:
        return {
            "score": 8,
            "feedback": f"""Score: 8
Strengths:
- You selected option {answer}

Mistakes:
- MCQ answer checking is currently basic because correct option is hidden from AI output

Better Answer:
For better MCQ accuracy, store the correct answer internally and compare it with user's selected option."""
        }

    return {
        "score": 3,
        "feedback": """Score: 3
Strengths:
- You attempted the MCQ

Mistakes:
- Please answer only A, B, C, or D

Better Answer:
Select one option like A, B, C, or D."""
    }


def extract_score(feedback):
    match = re.search(r"Score:\s*(10|[0-9])", feedback, re.IGNORECASE)
    return int(match.group(1)) if match else 5


def rule_based_evaluation(answer):
    words = answer.split()
    word_count = len(words)

    technical_words = [
        "example", "function", "class", "object", "database",
        "api", "framework", "model", "logic", "method",
        "django", "python", "view", "template", "url"
    ]

    keyword_count = sum(
        1 for word in technical_words
        if word.lower() in answer.lower()
    )

    if word_count < 5:
        score = 2
    elif word_count < 15:
        score = 5
    elif keyword_count >= 2:
        score = 8
    else:
        score = 6

    feedback = f"""Score: {score}
Strengths:
- You attempted the answer
- Your answer has {word_count} words

Mistakes:
- Add more technical keywords
- Add one practical example

Better Answer:
Start with a clear definition, explain the main point, and give one real-world example.
"""

    return {
        "score": score,
        "feedback": feedback
    }