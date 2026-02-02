# Simple Quiz Engine

A real-time quiz application with WebSocket communication and server-authoritative timing.

![Python](https://img.shields.io/badge/Python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-green)
![React](https://img.shields.io/badge/React-18-blue)
![WebSocket](https://img.shields.io/badge/WebSocket-Real--time-orange)

## Features

- **Real-time WebSocket communication** between client and server
- **Server-authoritative timer** - no client-side cheating
- **Question navigation** - go forward, back, or jump to any question
- **Time tracking** per question for analytics
- **Instant scoring** with detailed breakdown
- **Grade calculation** (A-F)

## Architecture
```
┌─────────────────┐         WebSocket          ┌─────────────────┐
│  React Frontend │◄──────────────────────────►│  FastAPI Backend │
│                 │                            │                  │
│  • Quiz UI      │   • timer_tick             │  • Quiz state    │
│  • Timer display│   • question_data          │  • Timer control │
│  • Answer input │   • answer_received        │  • Scoring       │
└─────────────────┘   • quiz_complete          └────────┬─────────┘
                                                        │
                                                        ▼
                                               ┌─────────────────┐
                                               │     SQLite      │
                                               └─────────────────┘
```

## Quick Start

### Backend
```bash
cd backend
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

## WebSocket Protocol

### Client → Server

| Message | Description |
|---------|-------------|
| `start_quiz` | Begin the quiz, start timer |
| `answer` | Submit answer for current question |
| `next_question` | Navigate to next question |
| `prev_question` | Navigate to previous question |
| `go_to_question` | Jump to specific question |
| `submit_quiz` | End quiz and get results |

### Server → Client

| Message | Description |
|---------|-------------|
| `connected` | Initial connection with quiz info |
| `question` | Question data to display |
| `timer_tick` | Time remaining update (every second) |
| `answer_received` | Confirmation of answer |
| `quiz_complete` | Final results and score |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/quizzes` | GET | List available quizzes |
| `/api/quizzes/{id}` | GET | Get quiz details |
| `/api/sessions` | POST | Create new quiz session |
| `/api/sessions/{id}` | GET | Get session status |
| `/ws/{session_id}` | WS | WebSocket connection |

## Project Structure
```
simple-quiz-engine/
├── backend/
│   ├── app/
│   │   ├── main.py        # FastAPI + WebSocket server
│   │   └── database.py    # SQLite database
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── QuizLobby.jsx
│   │   │   ├── QuizSession.jsx
│   │   │   └── QuizResults.jsx
│   │   ├── App.jsx
│   │   └── App.css
│   └── package.json
└── README.md
```

## Part of Ed-Tech Suite

This is a building block for the Adaptive Synchronous Testing Platform:

| Component | Repository |
|-----------|------------|
| [Question Bank MCP](https://github.com/woodstocksoftware/question-bank-mcp) | Question management |
| [Student Progress Tracker](https://github.com/woodstocksoftware/student-progress-tracker) | Performance tracking |
| **Simple Quiz Engine** | Real-time quiz delivery |

## License

MIT

---

Built by [Jim Williams](https://linkedin.com/in/woodstocksoftware) | [GitHub](https://github.com/woodstocksoftware)
