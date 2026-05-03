import sqlite3

DB_NAME = "interview_agent.db"


def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            preferred_topic TEXT DEFAULT 'Python'
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS interviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            topic TEXT NOT NULL,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            feedback TEXT NOT NULL,
            score INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    conn.commit()
    conn.close()


def create_user(name, email, password):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
        (name, email, password)
    )
    conn.commit()
    conn.close()


def get_user_by_email(email):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cur.fetchone()
    conn.close()
    return user


def get_user_by_id(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cur.fetchone()
    conn.close()
    return user


def update_preferred_topic(user_id, topic):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET preferred_topic = ? WHERE id = ?",
        (topic, user_id)
    )
    conn.commit()
    conn.close()


def save_interview(user_id, topic, question, answer, feedback, score):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO interviews (user_id, topic, question, answer, feedback, score)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, topic, question, answer, feedback, score))
    conn.commit()
    conn.close()


def get_user_interviews(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM interviews
        WHERE user_id = ?
        ORDER BY created_at DESC
    """, (user_id,))
    data = cur.fetchall()
    conn.close()
    return data


def get_dashboard_stats(user_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) AS total FROM interviews WHERE user_id = ?", (user_id,))
    total = cur.fetchone()["total"]

    cur.execute("SELECT AVG(score) AS avg_score FROM interviews WHERE user_id = ?", (user_id,))
    avg_score_row = cur.fetchone()
    avg_score = round(avg_score_row["avg_score"], 1) if avg_score_row["avg_score"] else 0

    cur.execute("""
        SELECT topic, score, created_at
        FROM interviews
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT 1
    """, (user_id,))
    last_attempt = cur.fetchone()

    cur.execute("""
        SELECT topic, AVG(score) AS topic_avg
        FROM interviews
        WHERE user_id = ?
        GROUP BY topic
        ORDER BY topic_avg ASC
        LIMIT 1
    """, (user_id,))
    weak_topic = cur.fetchone()

    cur.execute("""
        SELECT topic, AVG(score) AS topic_avg
        FROM interviews
        WHERE user_id = ?
        GROUP BY topic
        ORDER BY topic_avg DESC
        LIMIT 1
    """, (user_id,))
    best_topic = cur.fetchone()

    conn.close()

    return {
        "total": total,
        "avg_score": avg_score,
        "last_attempt": last_attempt,
        "weak_topic": weak_topic["topic"] if weak_topic else "No data",
        "best_topic": best_topic["topic"] if best_topic else "No data"
    }
    
def delete_interview_by_id(interview_id, user_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM interviews WHERE id = ? AND user_id = ?",
        (interview_id, user_id)
    )

    conn.commit()
    conn.close()