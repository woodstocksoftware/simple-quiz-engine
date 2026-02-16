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


# ── Navigation ────────────────────────────────────────────


def test_ws_prev_question(seeded_client):
    """Navigate backward to the previous question."""
    sid, token = _create_session(seeded_client)
    with seeded_client.websocket_connect(f"/ws/{sid}?token={token}") as ws:
        ws.receive_json()  # connected
        ws.send_json({"type": "start_quiz"})
        ws.receive_json()  # question 1

        # Go to question 2
        ws.send_json({"type": "next_question", "current": 1})
        msg = ws.receive_json()
        assert msg["question_number"] == 2

        # Go back to question 1
        ws.send_json({"type": "prev_question", "current": 2})
        msg = ws.receive_json()
        assert msg["type"] == "question"
        assert msg["question_number"] == 1


def test_ws_go_to_question(seeded_client):
    """Jump directly to a specific question number."""
    sid, token = _create_session(seeded_client)
    with seeded_client.websocket_connect(f"/ws/{sid}?token={token}") as ws:
        ws.receive_json()  # connected
        ws.send_json({"type": "start_quiz"})
        ws.receive_json()  # question 1

        # Jump to question 3
        ws.send_json({"type": "go_to_question", "question_number": 3})
        msg = ws.receive_json()
        assert msg["type"] == "question"
        assert msg["question_number"] == 3
        assert msg["total_questions"] == 3


def test_ws_go_to_question_invalid(seeded_client):
    """go_to_question with out-of-range number is silently ignored."""
    sid, token = _create_session(seeded_client)
    with seeded_client.websocket_connect(f"/ws/{sid}?token={token}") as ws:
        ws.receive_json()  # connected
        ws.send_json({"type": "start_quiz"})
        ws.receive_json()  # question 1

        # Jump to invalid question 0
        ws.send_json({"type": "go_to_question", "question_number": 0})
        # Jump to question beyond range
        ws.send_json({"type": "go_to_question", "question_number": 99})
        # Valid navigation still works after invalid ones
        ws.send_json({"type": "go_to_question", "question_number": 2})
        msg = ws.receive_json()
        assert msg["question_number"] == 2


def test_ws_navigate_out_of_bounds(seeded_client):
    """prev from question 1 and next from last question are no-ops."""
    sid, token = _create_session(seeded_client)
    with seeded_client.websocket_connect(f"/ws/{sid}?token={token}") as ws:
        ws.receive_json()  # connected
        ws.send_json({"type": "start_quiz"})
        ws.receive_json()  # question 1

        # prev from question 1 — no-op
        ws.send_json({"type": "prev_question", "current": 1})

        # next from last question — no-op
        ws.send_json({"type": "next_question", "current": 3})

        # Valid navigation still works
        ws.send_json({"type": "next_question", "current": 1})
        msg = ws.receive_json()
        assert msg["question_number"] == 2


def test_ws_navigate_invalid_current(seeded_client):
    """Navigate with bad current value is silently ignored."""
    sid, token = _create_session(seeded_client)
    with seeded_client.websocket_connect(f"/ws/{sid}?token={token}") as ws:
        ws.receive_json()  # connected
        ws.send_json({"type": "start_quiz"})
        ws.receive_json()  # question 1

        # Non-integer current
        ws.send_json({"type": "next_question", "current": "bad"})
        # Out-of-range current
        ws.send_json({"type": "next_question", "current": 0})
        ws.send_json({"type": "next_question", "current": 99})

        # Valid navigation still works
        ws.send_json({"type": "next_question", "current": 1})
        msg = ws.receive_json()
        assert msg["question_number"] == 2


# ── Error handling ────────────────────────────────────────


def test_ws_unknown_message_type(seeded_client):
    """Unknown message type gets an error response."""
    sid, token = _create_session(seeded_client)
    with seeded_client.websocket_connect(f"/ws/{sid}?token={token}") as ws:
        ws.receive_json()  # connected
        ws.send_json({"type": "start_quiz"})
        ws.receive_json()  # question 1

        ws.send_json({"type": "bogus_command"})
        msg = ws.receive_json()
        assert msg["type"] == "error"
        assert "Unknown message type" in msg["message"]


def test_ws_invalid_question_id(seeded_client):
    """Answer with a question ID not in the quiz gets an error."""
    sid, token = _create_session(seeded_client)
    with seeded_client.websocket_connect(f"/ws/{sid}?token={token}") as ws:
        ws.receive_json()  # connected
        ws.send_json({"type": "start_quiz"})
        ws.receive_json()  # question 1

        ws.send_json({"type": "answer", "question_id": "fake-id", "answer": "2"})
        msg = ws.receive_json()
        assert msg["type"] == "error"
        assert "Invalid question ID" in msg["message"]


# ── Guard / edge cases ───────────────────────────────────


def test_ws_double_start(seeded_client):
    """Starting a quiz that's already in_progress is a no-op."""
    sid, token = _create_session(seeded_client)
    with seeded_client.websocket_connect(f"/ws/{sid}?token={token}") as ws:
        ws.receive_json()  # connected
        ws.send_json({"type": "start_quiz"})
        ws.receive_json()  # question 1

        # Second start should be silently ignored
        ws.send_json({"type": "start_quiz"})

        # Normal operation still works
        ws.send_json({"type": "next_question", "current": 1})
        msg = ws.receive_json()
        assert msg["question_number"] == 2


def test_ws_duplicate_connection(seeded_client):
    """Second WebSocket to same session is rejected with 4009."""
    sid, token = _create_session(seeded_client)
    with seeded_client.websocket_connect(f"/ws/{sid}?token={token}") as ws:
        ws.receive_json()  # connected

        # Try to open second connection
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with seeded_client.websocket_connect(f"/ws/{sid}?token={token}"):
                pass
        assert exc_info.value.code == 4009


def test_ws_existing_answer_shown(seeded_client, seed_quiz):
    """When navigating back, the question payload includes existing_answer."""
    sid, token = _create_session(seeded_client)
    with seeded_client.websocket_connect(f"/ws/{sid}?token={token}") as ws:
        ws.receive_json()  # connected
        ws.send_json({"type": "start_quiz"})
        q1 = ws.receive_json()  # question 1
        assert q1["existing_answer"] is None

        # Answer question 1
        ws.send_json({"type": "answer", "question_id": "tq1", "answer": "2"})
        ws.receive_json()  # answer_received

        # Navigate away and back
        ws.send_json({"type": "next_question", "current": 1})
        ws.receive_json()  # question 2
        ws.send_json({"type": "prev_question", "current": 2})
        q1_again = ws.receive_json()  # question 1 again
        assert q1_again["existing_answer"] == "2"
