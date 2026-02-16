"""
Simple Quiz Engine - FastAPI WebSocket Server

Provides REST endpoints for quiz/session management and a WebSocket
endpoint for real-time quiz play with server-authoritative timing.
"""

import asyncio
import uuid
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import database as db

app = FastAPI(title="Simple Quiz Engine")

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# SESSION MANAGER
# ============================================================

class QuizSessionManager:
    """Manages active quiz sessions and their WebSocket connections."""

    def __init__(self) -> None:
        self.active_connections: dict[str, WebSocket] = {}
        self.session_tasks: dict[str, asyncio.Task] = {}
        self.question_start_times: dict[str, datetime] = {}

    async def connect(self, session_id: str, websocket: WebSocket) -> None:
        """Accept a WebSocket connection and register it."""
        await websocket.accept()
        self.active_connections[session_id] = websocket

    def disconnect(self, session_id: str) -> None:
        """Remove a session's connection, cancel its timer task, and clean up."""
        if session_id in self.active_connections:
            del self.active_connections[session_id]
        if session_id in self.session_tasks:
            self.session_tasks[session_id].cancel()
            del self.session_tasks[session_id]
        if session_id in self.question_start_times:
            del self.question_start_times[session_id]

    async def send_message(self, session_id: str, message: dict) -> None:
        """Send a JSON message to a connected client."""
        if session_id in self.active_connections:
            await self.active_connections[session_id].send_json(message)

    def start_question_timer(self, session_id: str) -> None:
        """Record the current time as the start of a question attempt."""
        self.question_start_times[session_id] = datetime.now()

    def get_question_time_spent(self, session_id: str) -> int:
        """Return seconds elapsed since the current question was started."""
        if session_id in self.question_start_times:
            delta = datetime.now() - self.question_start_times[session_id]
            return int(delta.total_seconds())
        return 0


manager = QuizSessionManager()


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

        # Update database
        db.update_session_time(session_id, time_remaining)

        # Send tick to client
        await manager.send_message(session_id, {
            "type": "timer_tick",
            "time_remaining": time_remaining
        })

        # Check if session still active
        session = db.get_session(session_id)
        if not session or session['status'] == 'completed':
            break

    # Time's up!
    if time_remaining <= 0:
        await end_quiz(session_id, reason="time_expired")


async def end_quiz(session_id: str, reason: str = "submitted") -> None:
    """End the quiz, calculate the score, and send results to the client."""
    score_data = db.calculate_score(session_id)
    db.complete_session(session_id, score_data['percentage'])

    responses = db.get_responses(session_id)
    session = db.get_session(session_id)
    questions = db.get_questions(session['quiz_id'])

    # Build results with correct answers
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
    quiz_id: str
    student_name: Optional[str] = None


@app.get("/api/quizzes")
async def list_quizzes() -> list[dict]:
    """List all available quizzes."""
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, description, time_limit_seconds FROM quizzes")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


@app.get("/api/quizzes/{quiz_id}")
async def get_quiz(quiz_id: str) -> dict:
    """Get quiz details including question count."""
    quiz = db.get_quiz(quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    questions = db.get_questions(quiz_id)
    quiz['question_count'] = len(questions)
    return quiz


@app.post("/api/sessions")
async def create_session(request: CreateSessionRequest) -> dict:
    """Create a new quiz session for a student."""
    quiz = db.get_quiz(request.quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    session_id = f"session-{uuid.uuid4().hex[:8]}"
    session = db.create_session(session_id, request.quiz_id, request.student_name)

    return session


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str) -> dict:
    """Get the current status and score of a session."""
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


# ============================================================
# WEBSOCKET ENDPOINT
# ============================================================

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str) -> None:
    """WebSocket connection for real-time quiz play.

    Sends initial quiz state on connect, then listens for client messages
    (start, answer, navigate, submit) until disconnect or completion.
    """
    session = db.get_session(session_id)
    if not session:
        await websocket.close(code=4004, reason="Session not found")
        return

    if session['status'] == 'completed':
        await websocket.close(code=4003, reason="Session already completed")
        return

    await manager.connect(session_id, websocket)

    try:
        quiz = db.get_quiz(session['quiz_id'])
        questions = db.get_questions(session['quiz_id'])

        # Send initial state
        await manager.send_message(session_id, {
            "type": "connected",
            "quiz": {
                "id": quiz['id'],
                "title": quiz['title'],
                "description": quiz['description'],
                "time_limit_seconds": quiz['time_limit_seconds'],
                "question_count": len(questions)
            },
            "session": {
                "id": session_id,
                "status": session['status'],
                "time_remaining": session['time_remaining_seconds'],
                "current_question": session['current_question']
            }
        })

        # Listen for messages
        while True:
            data = await websocket.receive_json()
            await handle_message(session_id, data, questions)

    except WebSocketDisconnect:
        manager.disconnect(session_id)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(session_id)


async def handle_message(session_id: str, data: dict,
                         questions: list[dict]) -> None:
    """Route an incoming WebSocket message to the appropriate handler."""
    msg_type = data.get("type")

    if msg_type == "start_quiz":
        # Start the quiz
        db.start_session(session_id)
        manager.start_question_timer(session_id)

        # Start timer task
        task = asyncio.create_task(run_timer(session_id))
        manager.session_tasks[session_id] = task

        # Send first question
        question = questions[0]
        await manager.send_message(session_id, {
            "type": "question",
            "question_number": 1,
            "total_questions": len(questions),
            "question": {
                "id": question['id'],
                "text": question['question_text'],
                "options": question['options']
            }
        })

    elif msg_type == "answer":
        # Record answer with time spent
        question_id = data.get("question_id")
        answer = data.get("answer")
        time_spent = manager.get_question_time_spent(session_id)

        db.save_response(session_id, question_id, answer, time_spent)

        await manager.send_message(session_id, {
            "type": "answer_received",
            "question_id": question_id,
            "time_spent": time_spent
        })

    elif msg_type == "next_question":
        current = data.get("current", 1)
        next_num = current + 1

        if next_num <= len(questions):
            db.update_current_question(session_id, next_num)
            manager.start_question_timer(session_id)

            question = questions[next_num - 1]
            await manager.send_message(session_id, {
                "type": "question",
                "question_number": next_num,
                "total_questions": len(questions),
                "question": {
                    "id": question['id'],
                    "text": question['question_text'],
                    "options": question['options']
                }
            })

    elif msg_type == "prev_question":
        current = data.get("current", 1)
        prev_num = current - 1

        if prev_num >= 1:
            db.update_current_question(session_id, prev_num)
            manager.start_question_timer(session_id)

            question = questions[prev_num - 1]

            # Get existing answer if any
            responses = db.get_responses(session_id)
            existing = next((r for r in responses if r['question_id'] == question['id']), None)

            await manager.send_message(session_id, {
                "type": "question",
                "question_number": prev_num,
                "total_questions": len(questions),
                "question": {
                    "id": question['id'],
                    "text": question['question_text'],
                    "options": question['options']
                },
                "existing_answer": existing['answer'] if existing else None
            })

    elif msg_type == "go_to_question":
        target = data.get("question_number", 1)

        if 1 <= target <= len(questions):
            db.update_current_question(session_id, target)
            manager.start_question_timer(session_id)

            question = questions[target - 1]

            # Get existing answer if any
            responses = db.get_responses(session_id)
            existing = next((r for r in responses if r['question_id'] == question['id']), None)

            await manager.send_message(session_id, {
                "type": "question",
                "question_number": target,
                "total_questions": len(questions),
                "question": {
                    "id": question['id'],
                    "text": question['question_text'],
                    "options": question['options']
                },
                "existing_answer": existing['answer'] if existing else None
            })

    elif msg_type == "submit_quiz":
        await end_quiz(session_id, reason="submitted")


# ============================================================
# STARTUP
# ============================================================

@app.on_event("startup")
async def startup() -> None:
    """Seed sample data on server startup."""
    db.seed_sample_quiz()
    print("Quiz Engine started!")
    print("Sample quiz available: demo-quiz")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
