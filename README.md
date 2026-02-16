# Simple Quiz Engine

Real-time WebSocket quiz engine for educational assessments. Students connect, answer timed questions, and receive instant scored results — all powered by server-authoritative timing to prevent client-side cheating.

[![Python](https://img.shields.io/badge/Python-3.12-3776ab?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-19-61dafb?logo=react&logoColor=black)](https://react.dev)
[![WebSocket](https://img.shields.io/badge/WebSocket-Real--time-orange)](https://developer.mozilla.org/en-US/docs/Web/API/WebSocket)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## Features

- **Real-time WebSocket communication** — instant question delivery, answer confirmation, and live timer updates
- **Server-authoritative timer** — countdown runs on the server, preventing client-side time manipulation
- **Live quiz sessions** — students connect by name, work through timed questions, and submit for grading
- **Question navigation** — move forward, backward, or jump to any question; change answers freely
- **Per-question time tracking** — measures how long each student spends on every question
- **Instant scoring** — automatic grading with percentage score, letter grade (A-F), and detailed breakdown
- **Multi-student support** — concurrent independent sessions against the same quiz

## Architecture

```
┌──────────────────┐         WebSocket          ┌──────────────────┐
│  React Frontend  │◄──────────────────────────►│  FastAPI Backend  │
│   (Vite dev)     │     JSON messages          │   (Uvicorn)      │
│                  │                            │                   │
│  QuizLobby       │  Client → Server:          │  Session Manager  │
│  QuizSession     │  ├─ start_quiz             │  Timer Task       │
│  QuizResults     │  ├─ answer                 │  Scoring Engine   │
│                  │  ├─ next/prev/go_to        │  Database Layer   │
└──────────────────┘  └─ submit_quiz            └────────┬──────────┘
                                                         │
                      Server → Client:                   ▼
                      ├─ connected              ┌──────────────────┐
                      ├─ question               │     SQLite       │
                      ├─ timer_tick             │                   │
                      ├─ answer_received        │  quizzes          │
                      └─ quiz_complete          │  questions        │
                                                │  sessions         │
                                                │  responses        │
                                                └──────────────────┘
```

**Session lifecycle:** `not_started` → `in_progress` → `completed`

The server runs an async timer task per session. Each second it decrements the remaining time, persists it to the database, and pushes a `timer_tick` to the client. When time expires, the quiz auto-submits.

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 18+

### 1. Start the backend

```bash
cd backend
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

The server starts at `http://localhost:8000` and seeds a sample quiz ("Python Fundamentals") on first run.

### 2. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` in your browser.

### 3. Take a quiz

1. Enter your name in the lobby
2. Select a quiz and click **Start Quiz**
3. Review the quiz info, then click **Begin Quiz**
4. Answer questions — navigate freely with the question buttons or Previous/Next
5. Click **Submit Quiz** (or let the timer run out)
6. Review your scored results with per-question breakdown

## Protocol Reference

### REST API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/quizzes` | List all available quizzes |
| `GET` | `/api/quizzes/{id}` | Get quiz details and question count |
| `POST` | `/api/sessions` | Create a new session (`{quiz_id, student_name}`) |
| `GET` | `/api/sessions/{id}` | Get session status and score |
| `WS` | `/ws/{session_id}` | WebSocket connection for quiz play |

### WebSocket Messages

**Client → Server:**

| Type | Payload | Description |
|------|---------|-------------|
| `start_quiz` | `{}` | Begin the quiz and start the server timer |
| `answer` | `{question_id, answer}` | Submit or update an answer |
| `next_question` | `{current}` | Navigate to the next question |
| `prev_question` | `{current}` | Navigate to the previous question |
| `go_to_question` | `{question_number}` | Jump to a specific question |
| `submit_quiz` | `{}` | End the quiz and receive results |

**Server → Client:**

| Type | Payload | Description |
|------|---------|-------------|
| `connected` | `{quiz, session}` | Connection established with quiz metadata and session state |
| `question` | `{question_number, total_questions, question, existing_answer?}` | Question data with any previously saved answer |
| `timer_tick` | `{time_remaining}` | Remaining seconds (sent every second) |
| `answer_received` | `{question_id, time_spent}` | Confirmation that answer was recorded |
| `quiz_complete` | `{reason, score, results}` | Final score, grade, and per-question breakdown |

### Example: Full Session Flow

```
Client                          Server
  │                                │
  │──── WS connect ───────────────►│
  │◄─── connected {quiz, session} ─│
  │                                │
  │──── start_quiz ───────────────►│
  │◄─── question {Q1} ────────────│
  │◄─── timer_tick {299} ─────────│
  │◄─── timer_tick {298} ─────────│
  │                                │
  │──── answer {q1, "8"} ────────►│
  │◄─── answer_received ──────────│
  │                                │
  │──── next_question {1} ────────►│
  │◄─── question {Q2} ────────────│
  │                                │
  │──── submit_quiz ──────────────►│
  │◄─── quiz_complete {score} ────│
  │                                │
```

## Usage Example: Host a Quiz Session

**Create a quiz programmatically** using the database module:

```python
from backend.app.database import create_quiz, add_question

create_quiz("my-quiz", "Geography Quiz", time_limit_seconds=180)

add_question("geo-1", "my-quiz", 1,
    question_text="What is the capital of France?",
    options=["London", "Berlin", "Paris", "Madrid"],
    correct_answer="Paris")

add_question("geo-2", "my-quiz", 2,
    question_text="Which ocean is the largest?",
    options=["Atlantic", "Indian", "Arctic", "Pacific"],
    correct_answer="Pacific")
```

**Create a session via the API:**

```bash
curl -X POST http://localhost:8000/api/sessions \
  -H "Content-Type: application/json" \
  -d '{"quiz_id": "my-quiz", "student_name": "Alice"}'
```

**Connect via WebSocket** at `ws://localhost:8000/ws/{session_id}` to begin the quiz.

## Project Structure

```
simple-quiz-engine/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI server, WebSocket handler, session manager
│   │   └── database.py      # SQLite schema, CRUD operations, seed data
│   ├── data/                # SQLite database (auto-created, gitignored)
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── QuizLobby.jsx    # Quiz selection and name entry
│   │   │   ├── QuizSession.jsx  # Live quiz interface with timer
│   │   │   └── QuizResults.jsx  # Score display and question breakdown
│   │   ├── App.jsx              # Root component, screen routing
│   │   ├── App.css              # All component styles
│   │   └── main.jsx             # React entry point
│   ├── vite.config.js
│   └── package.json
├── CLAUDE.md                # Developer reference
└── README.md
```

## Testing

```bash
# Backend
cd backend
pip install pytest httpx pytest-asyncio
pytest

# Frontend
cd frontend
npm test
```

> Tests are planned but not yet implemented. Contributions welcome!

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes (`git commit -m 'Add my feature'`)
4. Push to the branch (`git push origin feature/my-feature`)
5. Open a Pull Request

## License

[MIT](LICENSE)

## Part of the Ed-Tech Suite

This is a building block for the Adaptive Synchronous Testing Platform:

| Component | Repository |
|-----------|------------|
| [Question Bank MCP](https://github.com/woodstocksoftware/question-bank-mcp) | Question management via MCP |
| [Student Progress Tracker](https://github.com/woodstocksoftware/student-progress-tracker) | Performance analytics |
| **Simple Quiz Engine** | Real-time quiz delivery |

---

Built by [Jim Williams](https://linkedin.com/in/woodstocksoftware) | [GitHub](https://github.com/woodstocksoftware)
