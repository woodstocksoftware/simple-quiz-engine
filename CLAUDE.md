# CLAUDE.md

## Project Overview

Simple Quiz Engine - a real-time WebSocket quiz application for educational assessments. Part of the Adaptive Synchronous Testing Platform ed-tech suite.

## Tech Stack

**Backend:** Python 3.12, FastAPI 0.109+, Uvicorn, SQLite3, WebSockets, Pydantic
**Frontend:** React 19, Vite 7, vanilla CSS
**Protocol:** WebSocket (JSON messages) + REST API

## Project Structure

```
backend/
  app/main.py       - FastAPI server, WebSocket handler, session manager, REST endpoints
  app/database.py   - SQLite operations, schema, seed data
  requirements.txt  - Python dependencies
  data/quiz.db      - SQLite database (gitignored, auto-created)

frontend/
  src/App.jsx                    - Root component, screen routing
  src/components/QuizLobby.jsx   - Quiz selection + name entry
  src/components/QuizSession.jsx - WebSocket quiz interface + timer
  src/components/QuizResults.jsx - Score display + question breakdown
  src/App.css                    - All component styles
```

## Running Locally

```bash
# Backend (terminal 1)
cd backend
python3.12 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000

# Frontend (terminal 2)
cd frontend
npm install
npm run dev
```

Backend: http://localhost:8000 | Frontend: http://localhost:5173

## Testing

No test suite exists yet. Backend can be tested with pytest + httpx (for async FastAPI). Frontend can be tested with Vitest + React Testing Library.

## Architecture

- **Server-authoritative timer** — `run_timer()` async task decrements each second server-side, sends `timer_tick` to client. Client cannot manipulate time.
- **Session lifecycle** — `not_started` → `in_progress` → `completed`
- **Scoring** — earned points / possible points * 100, calculated from responses table
- **Answer upsert** — `ON CONFLICT(session_id, question_id) DO UPDATE` allows answer changes

## WebSocket Protocol

### Client → Server

| Type | Payload | Description |
|------|---------|-------------|
| `start_quiz` | `{}` | Begin quiz and start server timer |
| `answer` | `{question_id, answer}` | Submit/update answer |
| `next_question` | `{current}` | Navigate forward |
| `prev_question` | `{current}` | Navigate backward |
| `go_to_question` | `{question_number}` | Jump to specific question |
| `submit_quiz` | `{}` | End quiz, get results |

### Server → Client

| Type | Payload | Description |
|------|---------|-------------|
| `connected` | `{quiz, session}` | Connection established with metadata |
| `question` | `{question_number, total_questions, question, existing_answer?}` | Question data |
| `timer_tick` | `{time_remaining}` | Time update (every second) |
| `answer_received` | `{question_id, time_spent}` | Answer confirmation |
| `quiz_complete` | `{reason, score, results}` | Final results with breakdown |

## REST Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/quizzes` | List all quizzes |
| GET | `/api/quizzes/{id}` | Quiz details + question count |
| POST | `/api/sessions` | Create session `{quiz_id, student_name}` |
| GET | `/api/sessions/{id}` | Session status |
| WS | `/ws/{session_id}` | WebSocket connection |

## Database

SQLite with 4 tables: `quizzes`, `questions`, `sessions`, `responses`. Auto-created on import of `database.py`. Sample "demo-quiz" seeded on startup if not present.

## Key Design Decisions

- CORS allows all origins (`*`) for development simplicity
- Question options stored as JSON text in SQLite
- Time spent per question accumulated on answer updates (not replaced)
- WebSocket close codes: 4004 (session not found), 4003 (session completed)
- `@app.on_event("startup")` seeds sample data
