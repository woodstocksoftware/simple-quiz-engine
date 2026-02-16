# CLAUDE.md

## Project Overview

Simple Quiz Engine - a real-time WebSocket quiz application for educational assessments. Part of the Adaptive Synchronous Testing Platform ed-tech suite.

## Tech Stack

**Backend:** Python 3.12, FastAPI 0.109+, Uvicorn, SQLite3, WebSockets, Pydantic
**Frontend:** React 19, Vite 7, vanilla CSS
**Protocol:** WebSocket (JSON messages) + REST API
**Linting:** ruff (backend), eslint (frontend)

## Project Structure

```
backend/
  app/main.py       - FastAPI server, WebSocket handler, session manager, REST endpoints
  app/database.py   - SQLite operations, schema, seed data
  requirements.txt  - Python dependencies
  pyproject.toml    - ruff + pytest config
  data/quiz.db      - SQLite database (gitignored, auto-created)

frontend/
  src/App.jsx                         - Root component, screen routing, session persistence
  src/components/QuizLobby.jsx        - Quiz selection + name entry
  src/components/QuizSession.jsx      - WebSocket quiz interface + timer + reconnection
  src/components/QuizResults.jsx      - Score display + question breakdown
  src/components/ErrorBoundary.jsx    - React error boundary with reset
  src/config.js                       - API/WS URL configuration (env vars)
  src/utils/formatTime.js             - Shared time formatting utility
  src/App.css                         - All component styles

.github/workflows/ci.yml             - GitHub Actions CI (ruff, eslint, vite build)
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

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated allowed origins |
| `VITE_API_URL` | `http://localhost:8000` | Backend API URL (frontend) |
| `VITE_WS_URL` | `ws://localhost:8000` | Backend WebSocket URL (frontend) |

## Testing

No test suite exists yet. Backend can be tested with pytest + httpx (for async FastAPI). Frontend can be tested with Vitest + React Testing Library.

## Linting

```bash
# Backend
python3 -m ruff check backend/

# Frontend
cd frontend && npx eslint src/
```

## Architecture

- **Server-authoritative timer** — `run_timer()` async task decrements each second server-side, sends `timer_tick` to client. Client cannot manipulate time.
- **Session token auth** — Sessions created with `secrets.token_urlsafe(32)` token, validated on WebSocket connect via `secrets.compare_digest`. Token passed as query param.
- **Session lifecycle** — `not_started` → `in_progress` → `completed`
- **Scoring** — earned points / total possible points * 100, calculated from all quiz questions (not just answered ones)
- **Answer upsert** — `ON CONFLICT(session_id, question_id) DO UPDATE` allows answer changes. Time spent replaced on re-answer.
- **Input validation** — All WS messages validated: question_id must belong to quiz, answer must be a valid option, navigation values must be integers in range.
- **Connection management** — Max 200 concurrent WS connections. Duplicate connections rejected. Session creation rate-limited.
- **Reconnection** — Frontend reconnects with exponential backoff (max 5 attempts). Server restarts timer on reconnect for in-progress sessions.
- **Session persistence** — Frontend stores session in `sessionStorage` for page refresh survival.
- **Error boundary** — React ErrorBoundary catches render errors with graceful recovery.

## WebSocket Protocol

### Client → Server

| Type | Payload | Description |
|------|---------|-------------|
| `start_quiz` | `{}` | Begin quiz and start server timer |
| `answer` | `{question_id, answer}` | Submit/update answer (validated) |
| `next_question` | `{current}` | Navigate forward |
| `prev_question` | `{current}` | Navigate backward |
| `go_to_question` | `{question_number}` | Jump to specific question |
| `submit_quiz` | `{}` | End quiz, get results |

### Server → Client

| Type | Payload | Description |
|------|---------|-------------|
| `connected` | `{quiz, session}` | Connection established with metadata |
| `question` | `{question_number, total_questions, question, existing_answer?}` | Question data (no correct_answer) |
| `timer_tick` | `{time_remaining}` | Time update (every second) |
| `answer_received` | `{question_id, time_spent}` | Answer confirmation |
| `quiz_complete` | `{reason, score, results}` | Final results with breakdown |
| `error` | `{message}` | Error response |

## REST Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/quizzes` | List all quizzes |
| GET | `/api/quizzes/{id}` | Quiz details + question count |
| POST | `/api/sessions` | Create session `{quiz_id, student_name}` → returns `{id, token}` |
| GET | `/api/sessions/{id}` | Session status (excludes token/student_name) |
| WS | `/ws/{session_id}?token=` | WebSocket connection (token required) |

## Database

SQLite with 4 tables: `quizzes`, `questions`, `sessions`, `responses`. Auto-created on import of `database.py`. Sample "demo-quiz" seeded on startup if not present. Sessions table includes `token` column (auto-migrated).

## Key Design Decisions

- CORS restricted to `CORS_ORIGINS` env var (default: `http://localhost:5173`)
- Question options stored as JSON text in SQLite
- `correct_answer` excluded from client-facing question data
- WebSocket close codes: 4001 (invalid token), 4004 (session not found), 4003 (session completed), 4009 (already connected)
- Lifespan context manager for startup/shutdown (not deprecated `on_event`)
- Backend binds to 127.0.0.1 by default
