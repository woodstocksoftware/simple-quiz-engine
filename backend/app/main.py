"""
Simple Quiz Engine - FastAPI WebSocket Server

Provides REST endpoints for quiz/session management and a WebSocket
endpoint for real-time quiz play with server-authoritative timing.
"""

import asyncio
import logging
import os
import secrets
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import database as db

logger = logging.getLogger(__name__)

# Configuration via environment variables
ALLOWED_ORIGINS = os.environ.get(
    "CORS_ORIGINS", "http://localhost:5173"
).split(",")
MAX_CONNECTIONS = int(os.environ.get("MAX_WS_CONNECTIONS", "200"))
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX = 30  # max session creations per IP per window


# ============================================================
# LIFESPAN
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Seed sample data on startup."""
    db.seed_sample_quiz()
    logger.info("Quiz Engine started")
    yield


app = FastAPI(title="Simple Quiz Engine", lifespan=lifespan)

# CORS for frontend — restricted origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# RATE LIMITER (in-memory)
# ============================================================

_rate_limit_store: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(client_ip: str) -> bool:
    """Return True if the client is within the rate limit."""
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW
    # Prune old entries
    _rate_limit_store[client_ip] = [
        t for t in _rate_limit_store[client_ip] if t > window_start
    ]
    if len(_rate_limit_store[client_ip]) >= RATE_LIMIT_MAX:
        return False
    _rate_limit_store[client_ip].append(now)
    return True


# ============================================================
# SESSION MANAGER
# ============================================================

class QuizSessionManager:
    """Manages active quiz sessions and their WebSocket connections."""

    def __init__(self) -> None:
        self.active_connections: dict[str, WebSocket] = {}
        self.session_tasks: dict[str, asyncio.Task] = {}
        self.question_start_times: dict[str, datetime] = {}

    def is_connected(self, session_id: str) -> bool:
        """Check if a session already has an active WebSocket connection."""
        return session_id in self.active_connections

    async def connect(self, session_id: str, websocket: WebSocket) -> None:
        """Accept a WebSocket connection and register it."""
        await websocket.accept()
        self.active_connections[session_id] = websocket

    def disconnect(self, session_id: str) -> None:
        """Remove a session's connection, cancel its timer task, and clean up."""
        self.active_connections.pop(session_id, None)
        task = self.session_tasks.pop(session_id, None)
        if task:
            task.cancel()
        self.question_start_times.pop(session_id, None)

    async def send_message(self, session_id: str, message: dict) -> None:
        """Send a JSON message to a connected client."""
        ws = self.active_connections.get(session_id)
        if ws:
            try:
                await ws.send_json(message)
            except Exception:
                pass  # Connection may have closed

    def start_question_timer(self, session_id: str) -> None:
        """Record the current time as the start of a question attempt."""
        self.question_start_times[session_id] = datetime.now()

    def get_question_time_spent(self, session_id: str) -> int:
        """Return seconds elapsed since the current question was started."""
        start = self.question_start_times.get(session_id)
        if start:
            delta = datetime.now() - start
            return int(delta.total_seconds())
        return 0


manager = QuizSessionManager()


# ============================================================
# HELPERS
# ============================================================

def _build_question_ids(questions: list[dict]) -> set[str]:
    """Build a set of valid question IDs from a questions list."""
    return {q['id'] for q in questions}


def _build_question_options(questions: list[dict]) -> dict[str, list[str]]:
    """Build a map of question_id -> valid option strings."""
    return {q['id']: [str(o) for o in q['options']] for q in questions}


def _get_existing_answer(session_id: str, question_id: str) -> Optional[str]:
    """Look up an existing answer for a question in this session."""
    responses = db.get_responses(session_id)
    existing = next((r for r in responses if r['question_id'] == question_id), None)
    return existing['answer'] if existing else None


def _send_question(session_id: str, question: dict, question_number: int,
                   total_questions: int) -> dict:
    """Build a question message payload."""
    existing_answer = _get_existing_answer(session_id, question['id'])
    return {
        "type": "question",
        "question_number": question_number,
        "total_questions": total_questions,
        "question": {
            "id": question['id'],
            "text": question['question_text'],
            "options": question['options']
        },
        "existing_answer": existing_answer
    }


# ============================================================
# TIMER TASK
# ============================================================

async def run_timer(session_id: str) -> None:
    """Server-authoritative timer that ticks every second.

    Decrements time_remaining in the database, sends timer_tick messages
    to the client, and auto-submits the quiz when time expires.
    """
    session = db.get_session(session_id)
    if not session:
        return

    time_remaining: int = session['time_remaining_seconds']

    while time_remaining > 0:
        await asyncio.sleep(1)
        time_remaining -= 1

        db.update_session_time(session_id, time_remaining)

        await manager.send_message(session_id, {
            "type": "timer_tick",
            "time_remaining": time_remaining
        })

        # Check if session still active
        session = db.get_session(session_id)
        if not session or session['status'] == 'completed':
            break

    if time_remaining <= 0:
        await end_quiz(session_id, reason="time_expired")


async def end_quiz(session_id: str, reason: str = "submitted") -> None:
    """End the quiz, calculate the score, and send results to the client."""
    # Prevent double-completion
    session = db.get_session(session_id)
    if not session or session['status'] == 'completed':
        return

    score_data = db.calculate_score(session_id)
    db.complete_session(session_id, score_data['percentage'])

    responses = db.get_responses(session_id)
    session = db.get_session(session_id)
    questions = db.get_questions(session['quiz_id'])

    results: list[dict] = []
    for q in questions:
        response = next((r for r in responses if r['question_id'] == q['id']), None)
        results.append({
            "question_number": q['question_number'],
            "question_text": q['question_text'],
            "correct_answer": q['correct_answer'],
            "your_answer": response['answer'] if response else None,
            "is_correct": bool(response['is_correct']) if response else False,
            "time_spent": response['time_spent_seconds'] if response else 0
        })

    await manager.send_message(session_id, {
        "type": "quiz_complete",
        "reason": reason,
        "score": score_data,
        "results": results
    })

    manager.disconnect(session_id)


# ============================================================
# REST ENDPOINTS
# ============================================================

class CreateSessionRequest(BaseModel):
    """Request body for creating a new quiz session."""
    quiz_id: str = Field(..., max_length=100)
    student_name: Optional[str] = Field(None, max_length=200)


@app.get("/api/quizzes")
async def list_quizzes() -> list[dict]:
    """List all available quizzes."""
    conn = db.get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, description, time_limit_seconds FROM quizzes")
        rows = cursor.fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows]


@app.get("/api/quizzes/{quiz_id}")
async def get_quiz(quiz_id: str) -> dict:
    """Get quiz details including question count."""
    if len(quiz_id) > 100:
        raise HTTPException(status_code=400, detail="Invalid quiz ID")
    quiz = db.get_quiz(quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    questions = db.get_questions_for_client(quiz_id)
    quiz['question_count'] = len(questions)
    return quiz


@app.post("/api/sessions")
async def create_session(request: CreateSessionRequest) -> dict:
    """Create a new quiz session for a student."""
    quiz = db.get_quiz(request.quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    session_id = f"session-{secrets.token_urlsafe(24)}"
    token = secrets.token_urlsafe(32)
    session = db.create_session(
        session_id, request.quiz_id, token, request.student_name
    )

    return session


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str) -> dict:
    """Get the current status of a session (excludes token and student_name)."""
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    # Don't expose token or student_name to unauthenticated callers
    return {
        "id": session['id'],
        "quiz_id": session['quiz_id'],
        "status": session['status'],
        "time_remaining_seconds": session['time_remaining_seconds'],
        "current_question": session['current_question'],
        "score": session['score']
    }


# ============================================================
# WEBSOCKET ENDPOINT
# ============================================================

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
    token: str = Query(default=""),
) -> None:
    """WebSocket connection for real-time quiz play.

    Requires a valid session token passed as a query parameter.
    Rejects duplicate connections to the same session.
    """
    # Validate session exists
    session = db.get_session(session_id)
    if not session:
        await websocket.close(code=4004, reason="Session not found")
        return

    if session['status'] == 'completed':
        await websocket.close(code=4003, reason="Session already completed")
        return

    # Validate token
    if not token or not secrets.compare_digest(token, session.get('token', '')):
        await websocket.close(code=4001, reason="Invalid token")
        return

    # Reject duplicate connections
    if manager.is_connected(session_id):
        await websocket.close(code=4009, reason="Session already connected")
        return

    # Check connection limit
    if len(manager.active_connections) >= MAX_CONNECTIONS:
        await websocket.close(code=4029, reason="Server at capacity")
        return

    await manager.connect(session_id, websocket)

    try:
        questions = db.get_questions_for_client(session['quiz_id'])
        question_ids = _build_question_ids(questions)
        question_options = _build_question_options(questions)

        # Send initial state
        await manager.send_message(session_id, {
            "type": "connected",
            "quiz": {
                "id": session['quiz_id'],
                "title": db.get_quiz(session['quiz_id'])['title'],
                "description": db.get_quiz(session['quiz_id'])['description'],
                "time_limit_seconds": db.get_quiz(session['quiz_id'])['time_limit_seconds'],
                "question_count": len(questions)
            },
            "session": {
                "id": session_id,
                "status": session['status'],
                "time_remaining": session['time_remaining_seconds'],
                "current_question": session['current_question']
            }
        })

        # If session is already in_progress (reconnection), restart timer
        if session['status'] == 'in_progress':
            if session_id not in manager.session_tasks:
                manager.start_question_timer(session_id)
                task = asyncio.create_task(run_timer(session_id))
                manager.session_tasks[session_id] = task

        # Listen for messages
        while True:
            data = await websocket.receive_json()
            await handle_message(session_id, data, questions,
                                 question_ids, question_options)

    except WebSocketDisconnect:
        manager.disconnect(session_id)
    except Exception as e:
        logger.exception("WebSocket error for session %s: %s", session_id, e)
        manager.disconnect(session_id)


async def handle_message(session_id: str, data: dict,
                         questions: list[dict], question_ids: set[str],
                         question_options: dict[str, list[str]]) -> None:
    """Route an incoming WebSocket message to the appropriate handler.

    Validates all input before processing. Bad messages get an error response
    rather than crashing the connection.
    """
    msg_type = data.get("type")

    try:
        if msg_type == "start_quiz":
            await _handle_start_quiz(session_id, questions)

        elif msg_type == "answer":
            await _handle_answer(session_id, data, question_ids, question_options)

        elif msg_type == "next_question":
            await _handle_navigate(session_id, data, questions, direction=1)

        elif msg_type == "prev_question":
            await _handle_navigate(session_id, data, questions, direction=-1)

        elif msg_type == "go_to_question":
            await _handle_goto(session_id, data, questions)

        elif msg_type == "submit_quiz":
            await end_quiz(session_id, reason="submitted")

        else:
            await manager.send_message(session_id, {
                "type": "error",
                "message": f"Unknown message type: {msg_type}"
            })

    except Exception as e:
        logger.warning("Error handling message %s for %s: %s", msg_type, session_id, e)
        await manager.send_message(session_id, {
            "type": "error",
            "message": "Failed to process message"
        })


async def _handle_start_quiz(session_id: str, questions: list[dict]) -> None:
    """Start the quiz if it hasn't been started yet."""
    # Guard against double-start
    session = db.get_session(session_id)
    if not session or session['status'] != 'not_started':
        return

    db.start_session(session_id)
    manager.start_question_timer(session_id)

    # Only create timer if one doesn't exist
    if session_id not in manager.session_tasks:
        task = asyncio.create_task(run_timer(session_id))
        manager.session_tasks[session_id] = task

    question = questions[0]
    msg = _send_question(session_id, question, 1, len(questions))
    await manager.send_message(session_id, msg)


async def _handle_answer(session_id: str, data: dict,
                         question_ids: set[str],
                         question_options: dict[str, list[str]]) -> None:
    """Validate and record an answer."""
    question_id = data.get("question_id")
    answer = data.get("answer")

    # Validate question_id is a string belonging to this quiz
    if not isinstance(question_id, str) or question_id not in question_ids:
        await manager.send_message(session_id, {
            "type": "error", "message": "Invalid question ID"
        })
        return

    # Validate answer is a string and one of the valid options
    if not isinstance(answer, str) or answer not in question_options.get(question_id, []):
        await manager.send_message(session_id, {
            "type": "error", "message": "Invalid answer"
        })
        return

    time_spent = manager.get_question_time_spent(session_id)
    db.save_response(session_id, question_id, answer, time_spent)

    await manager.send_message(session_id, {
        "type": "answer_received",
        "question_id": question_id,
        "time_spent": time_spent
    })


async def _handle_navigate(session_id: str, data: dict,
                           questions: list[dict], direction: int) -> None:
    """Navigate forward or backward one question."""
    current = data.get("current")
    if not isinstance(current, int) or current < 1 or current > len(questions):
        return

    target = current + direction
    if target < 1 or target > len(questions):
        return

    db.update_current_question(session_id, target)
    manager.start_question_timer(session_id)

    question = questions[target - 1]
    msg = _send_question(session_id, question, target, len(questions))
    await manager.send_message(session_id, msg)


async def _handle_goto(session_id: str, data: dict,
                       questions: list[dict]) -> None:
    """Jump to a specific question number."""
    target = data.get("question_number")
    if not isinstance(target, int) or target < 1 or target > len(questions):
        return

    db.update_current_question(session_id, target)
    manager.start_question_timer(session_id)

    question = questions[target - 1]
    msg = _send_question(session_id, question, target, len(questions))
    await manager.send_message(session_id, msg)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
