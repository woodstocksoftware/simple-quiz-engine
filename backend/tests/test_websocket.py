"""Tests for WebSocket endpoint and message handling."""

import pytest
from starlette.websockets import WebSocketDisconnect


def _create_session(client):
    """Helper: create a session and return (session_id, token)."""
    resp = client.post("/api/sessions", json={
        "quiz_id": "test-quiz", "student_name": "Tester"
    })
    data = resp.json()
    return data["id"], data["token"]


# ── Auth / connection ──────────────────────────────────────


def test_ws_connect_valid_token(seeded_client):
    sid, token = _create_session(seeded_client)
    with seeded_client.websocket_connect(f"/ws/{sid}?token={token}") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "connected"
        assert msg["quiz"]["id"] == "test-quiz"
        assert msg["session"]["id"] == sid


def test_ws_connect_invalid_token(seeded_client):
    sid, _ = _create_session(seeded_client)
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with seeded_client.websocket_connect(f"/ws/{sid}?token=bad-token"):
            pass
    assert exc_info.value.code == 4001


def test_ws_connect_missing_session(seeded_client):
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with seeded_client.websocket_connect("/ws/nonexistent?token=x"):
            pass
    assert exc_info.value.code == 4004


def test_ws_connect_completed_session(seeded_client, seed_quiz):
    sid, token = _create_session(seeded_client)
    seed_quiz.start_session(sid)
    seed_quiz.complete_session(sid, 100.0)
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with seeded_client.websocket_connect(f"/ws/{sid}?token={token}"):
            pass
    assert exc_info.value.code == 4003


# ── Quiz flow ──────────────────────────────────────────────


def test_ws_start_quiz_sends_first_question(seeded_client):
    sid, token = _create_session(seeded_client)
    with seeded_client.websocket_connect(f"/ws/{sid}?token={token}") as ws:
        ws.receive_json()  # connected
        ws.send_json({"type": "start_quiz"})
        msg = ws.receive_json()
        assert msg["type"] == "question"
        assert msg["question_number"] == 1
        assert msg["total_questions"] == 3
        assert "id" in msg["question"]
        assert "text" in msg["question"]
        assert "options" in msg["question"]


def test_ws_answer_and_navigate(seeded_client):
    sid, token = _create_session(seeded_client)
    with seeded_client.websocket_connect(f"/ws/{sid}?token={token}") as ws:
        ws.receive_json()  # connected
        ws.send_json({"type": "start_quiz"})
        ws.receive_json()  # question 1

        # Answer question 1
        ws.send_json({"type": "answer", "question_id": "tq1", "answer": "2"})
        msg = ws.receive_json()
        assert msg["type"] == "answer_received"
        assert msg["question_id"] == "tq1"

        # Navigate to question 2
        ws.send_json({"type": "next_question", "current": 1})
        msg = ws.receive_json()
        assert msg["type"] == "question"
        assert msg["question_number"] == 2


def test_ws_submit_quiz(seeded_client):
    sid, token = _create_session(seeded_client)
    with seeded_client.websocket_connect(f"/ws/{sid}?token={token}") as ws:
        ws.receive_json()  # connected
        ws.send_json({"type": "start_quiz"})
        ws.receive_json()  # question 1

        # Answer and submit
        ws.send_json({"type": "answer", "question_id": "tq1", "answer": "2"})
        ws.receive_json()  # answer_received

        ws.send_json({"type": "submit_quiz"})
        msg = ws.receive_json()
        assert msg["type"] == "quiz_complete"
        assert msg["reason"] == "submitted"
        assert "score" in msg
        assert "results" in msg
        assert msg["score"]["answered"] == 1
        assert msg["score"]["correct"] == 1


def test_ws_invalid_answer_rejected(seeded_client):
    sid, token = _create_session(seeded_client)
    with seeded_client.websocket_connect(f"/ws/{sid}?token={token}") as ws:
        ws.receive_json()  # connected
        ws.send_json({"type": "start_quiz"})
        ws.receive_json()  # question 1

        # Send an invalid answer value
        ws.send_json({"type": "answer", "question_id": "tq1", "answer": "99"})
        msg = ws.receive_json()
        assert msg["type"] == "error"
        assert "Invalid answer" in msg["message"]
