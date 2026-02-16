"""
Simple Quiz Engine - Database

SQLite database layer for quizzes, questions, sessions, and responses.
Handles schema creation, CRUD operations, scoring, and seed data.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

DATABASE_PATH = Path(__file__).parent.parent / "data" / "quiz.db"


def get_connection() -> sqlite3.Connection:
    """Create and return a new SQLite connection with Row factory enabled."""
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_database() -> None:
    """Create all tables and indexes if they don't already exist."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        -- Quizzes
        CREATE TABLE IF NOT EXISTS quizzes (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            time_limit_seconds INTEGER NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        -- Questions
        CREATE TABLE IF NOT EXISTS questions (
            id TEXT PRIMARY KEY,
            quiz_id TEXT NOT NULL,
            question_number INTEGER NOT NULL,
            question_text TEXT NOT NULL,
            question_type TEXT DEFAULT 'multiple_choice',
            options TEXT,  -- JSON array
            correct_answer TEXT NOT NULL,
            points INTEGER DEFAULT 1,
            FOREIGN KEY (quiz_id) REFERENCES quizzes(id)
        );

        -- Quiz Sessions (a student taking a quiz)
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            quiz_id TEXT NOT NULL,
            student_name TEXT,
            started_at TEXT,
            completed_at TEXT,
            time_remaining_seconds INTEGER,
            current_question INTEGER DEFAULT 1,
            status TEXT DEFAULT 'not_started',  -- not_started, in_progress, completed
            score REAL,
            FOREIGN KEY (quiz_id) REFERENCES quizzes(id)
        );

        -- Responses
        CREATE TABLE IF NOT EXISTS responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            question_id TEXT NOT NULL,
            answer TEXT,
            is_correct INTEGER,
            time_spent_seconds INTEGER DEFAULT 0,
            answered_at TEXT,
            FOREIGN KEY (session_id) REFERENCES sessions(id),
            FOREIGN KEY (question_id) REFERENCES questions(id),
            UNIQUE(session_id, question_id)
        );

        CREATE INDEX IF NOT EXISTS idx_questions_quiz ON questions(quiz_id);
        CREATE INDEX IF NOT EXISTS idx_sessions_quiz ON sessions(quiz_id);
        CREATE INDEX IF NOT EXISTS idx_responses_session ON responses(session_id);
    """)

    conn.commit()
    conn.close()


init_database()


# ============================================================
# QUIZ OPERATIONS
# ============================================================

def create_quiz(quiz_id: str, title: str, time_limit_seconds: int,
                description: Optional[str] = None) -> dict:
    """Insert a new quiz and return its basic info."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO quizzes (id, title, description, time_limit_seconds)
        VALUES (?, ?, ?, ?)
    """, (quiz_id, title, description, time_limit_seconds))

    conn.commit()
    conn.close()

    return {"id": quiz_id, "title": title, "time_limit_seconds": time_limit_seconds}


def get_quiz(quiz_id: str) -> Optional[dict]:
    """Fetch a quiz by ID, or return None if not found."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM quizzes WHERE id = ?", (quiz_id,))
    row = cursor.fetchone()
    conn.close()

    return dict(row) if row else None


def add_question(question_id: str, quiz_id: str, question_number: int,
                 question_text: str, options: list, correct_answer: str,
                 points: int = 1) -> dict:
    """Add a question to a quiz. Options are stored as a JSON string."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO questions (id, quiz_id, question_number, question_text,
                               options, correct_answer, points)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (question_id, quiz_id, question_number, question_text,
          json.dumps(options), correct_answer, points))

    conn.commit()
    conn.close()

    return {"id": question_id, "question_number": question_number}


def get_questions(quiz_id: str) -> list[dict]:
    """Return all questions for a quiz, ordered by question_number."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM questions WHERE quiz_id = ? ORDER BY question_number
    """, (quiz_id,))

    rows = cursor.fetchall()
    conn.close()

    questions: list[dict] = []
    for row in rows:
        q = dict(row)
        q['options'] = json.loads(q['options']) if q['options'] else []
        questions.append(q)

    return questions


def get_question(question_id: str) -> Optional[dict]:
    """Fetch a single question by ID with parsed options."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM questions WHERE id = ?", (question_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        q = dict(row)
        q['options'] = json.loads(q['options']) if q['options'] else []
        return q
    return None


# ============================================================
# SESSION OPERATIONS
# ============================================================

def create_session(session_id: str, quiz_id: str,
                   student_name: Optional[str] = None) -> dict:
    """Create a new quiz session with time inherited from the quiz."""
    conn = get_connection()
    cursor = conn.cursor()

    quiz = get_quiz(quiz_id)
    if not quiz:
        raise ValueError(f"Quiz not found: {quiz_id}")

    cursor.execute("""
        INSERT INTO sessions (id, quiz_id, student_name, time_remaining_seconds, status)
        VALUES (?, ?, ?, ?, 'not_started')
    """, (session_id, quiz_id, student_name, quiz['time_limit_seconds']))

    conn.commit()
    conn.close()

    return {
        "id": session_id,
        "quiz_id": quiz_id,
        "student_name": student_name,
        "time_remaining_seconds": quiz['time_limit_seconds'],
        "status": "not_started"
    }


def get_session(session_id: str) -> Optional[dict]:
    """Fetch a session by ID, or return None if not found."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
    row = cursor.fetchone()
    conn.close()

    return dict(row) if row else None


def start_session(session_id: str) -> Optional[dict]:
    """Mark a session as in_progress and record the start time."""
    conn = get_connection()
    cursor = conn.cursor()

    now = datetime.now().isoformat()
    cursor.execute("""
        UPDATE sessions SET status = 'in_progress', started_at = ?
        WHERE id = ? AND status = 'not_started'
    """, (now, session_id))

    conn.commit()
    conn.close()

    return get_session(session_id)


def update_session_time(session_id: str, time_remaining: int) -> None:
    """Persist the current remaining time for a session."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE sessions SET time_remaining_seconds = ? WHERE id = ?
    """, (time_remaining, session_id))

    conn.commit()
    conn.close()


def update_current_question(session_id: str, question_number: int) -> None:
    """Update which question the student is currently viewing."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE sessions SET current_question = ? WHERE id = ?
    """, (question_number, session_id))

    conn.commit()
    conn.close()


def complete_session(session_id: str, score: float) -> Optional[dict]:
    """Mark a session as completed with the final score."""
    conn = get_connection()
    cursor = conn.cursor()

    now = datetime.now().isoformat()
    cursor.execute("""
        UPDATE sessions SET status = 'completed', completed_at = ?, score = ?
        WHERE id = ?
    """, (now, score, session_id))

    conn.commit()
    conn.close()

    return get_session(session_id)


# ============================================================
# RESPONSE OPERATIONS
# ============================================================

def save_response(session_id: str, question_id: str, answer: str,
                  time_spent_seconds: int = 0) -> dict:
    """Save or update a student's answer. Time spent accumulates on re-answers."""
    conn = get_connection()
    cursor = conn.cursor()

    # Check if correct
    question = get_question(question_id)
    is_correct = 1 if question and answer == question['correct_answer'] else 0

    now = datetime.now().isoformat()

    cursor.execute("""
        INSERT INTO responses (session_id, question_id, answer, is_correct,
                               time_spent_seconds, answered_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(session_id, question_id) DO UPDATE SET
            answer = excluded.answer,
            is_correct = excluded.is_correct,
            time_spent_seconds = time_spent_seconds + excluded.time_spent_seconds,
            answered_at = excluded.answered_at
    """, (session_id, question_id, answer, is_correct, time_spent_seconds, now))

    conn.commit()
    conn.close()

    return {"question_id": question_id, "answer": answer, "is_correct": bool(is_correct)}


def get_responses(session_id: str) -> list[dict]:
    """Return all responses for a session, joined with question metadata."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT r.*, q.question_number, q.correct_answer, q.points
        FROM responses r
        JOIN questions q ON q.id = r.question_id
        WHERE r.session_id = ?
        ORDER BY q.question_number
    """, (session_id,))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def calculate_score(session_id: str) -> dict:
    """Calculate earned points, possible points, and percentage for a session."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            SUM(CASE WHEN r.is_correct = 1 THEN q.points ELSE 0 END) as earned,
            SUM(q.points) as possible,
            COUNT(*) as answered,
            SUM(r.is_correct) as correct
        FROM responses r
        JOIN questions q ON q.id = r.question_id
        WHERE r.session_id = ?
    """, (session_id,))

    row = cursor.fetchone()
    conn.close()

    if row and row['possible']:
        return {
            "earned": row['earned'] or 0,
            "possible": row['possible'],
            "answered": row['answered'],
            "correct": row['correct'] or 0,
            "percentage": (row['earned'] or 0) / row['possible'] * 100
        }

    return {"earned": 0, "possible": 0, "answered": 0, "correct": 0, "percentage": 0}


# ============================================================
# SEED DATA
# ============================================================

def seed_sample_quiz() -> None:
    """Create a sample quiz for testing if it doesn't already exist."""
    if get_quiz("demo-quiz"):
        return

    create_quiz(
        quiz_id="demo-quiz",
        title="Python Fundamentals Quiz",
        description="Test your Python knowledge!",
        time_limit_seconds=300  # 5 minutes
    )

    questions = [
        {
            "id": "q1",
            "text": "What is the output of print(2 ** 3)?",
            "options": ["6", "8", "9", "5"],
            "answer": "8"
        },
        {
            "id": "q2",
            "text": "Which keyword is used to define a function in Python?",
            "options": ["function", "def", "func", "define"],
            "answer": "def"
        },
        {
            "id": "q3",
            "text": "What data type is the result of: 3 / 2?",
            "options": ["int", "float", "str", "bool"],
            "answer": "float"
        },
        {
            "id": "q4",
            "text": "Which of these is a mutable data type?",
            "options": ["tuple", "string", "list", "int"],
            "answer": "list"
        },
        {
            "id": "q5",
            "text": "What does 'len([1, 2, 3])' return?",
            "options": ["1", "2", "3", "4"],
            "answer": "3"
        }
    ]

    for i, q in enumerate(questions, 1):
        add_question(
            question_id=q["id"],
            quiz_id="demo-quiz",
            question_number=i,
            question_text=q["text"],
            options=q["options"],
            correct_answer=q["answer"]
        )

    print("Sample quiz created: demo-quiz")


if __name__ == "__main__":
    seed_sample_quiz()
    print("Database initialized!")
