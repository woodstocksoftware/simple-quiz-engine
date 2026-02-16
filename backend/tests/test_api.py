"""Tests for REST API endpoints (app/main.py)."""


# ── GET /api/quizzes ───────────────────────────────────────


def test_list_quizzes_empty(client):
    resp = client.get("/api/quizzes")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_quizzes(seeded_client):
    resp = seeded_client.get("/api/quizzes")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["id"] == "test-quiz"
    assert data[0]["title"] == "Test Quiz"


# ── GET /api/quizzes/{quiz_id} ─────────────────────────────


def test_get_quiz(seeded_client):
    resp = seeded_client.get("/api/quizzes/test-quiz")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "test-quiz"
    assert data["question_count"] == 3


def test_get_quiz_not_found(client):
    resp = client.get("/api/quizzes/nonexistent")
    assert resp.status_code == 404


# ── POST /api/sessions ────────────────────────────────────


def test_create_session(seeded_client):
    resp = seeded_client.post("/api/sessions", json={
        "quiz_id": "test-quiz",
        "student_name": "Alice"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["quiz_id"] == "test-quiz"
    assert data["student_name"] == "Alice"
    assert data["status"] == "not_started"
    assert "token" in data
    assert "id" in data


def test_create_session_without_name(seeded_client):
    resp = seeded_client.post("/api/sessions", json={
        "quiz_id": "test-quiz"
    })
    assert resp.status_code == 200
    assert resp.json()["student_name"] is None


def test_create_session_quiz_not_found(client):
    resp = client.post("/api/sessions", json={
        "quiz_id": "nonexistent"
    })
    assert resp.status_code == 404


def test_create_session_missing_quiz_id(seeded_client):
    resp = seeded_client.post("/api/sessions", json={})
    assert resp.status_code == 422


# ── GET /api/sessions/{session_id} ─────────────────────────


def test_get_session(seeded_client):
    create = seeded_client.post("/api/sessions", json={
        "quiz_id": "test-quiz", "student_name": "Bob"
    })
    session_id = create.json()["id"]

    resp = seeded_client.get(f"/api/sessions/{session_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == session_id
    assert data["status"] == "not_started"


def test_get_session_excludes_sensitive_fields(seeded_client):
    """GET session must not expose token or student_name."""
    create = seeded_client.post("/api/sessions", json={
        "quiz_id": "test-quiz", "student_name": "Secret"
    })
    session_id = create.json()["id"]

    resp = seeded_client.get(f"/api/sessions/{session_id}")
    data = resp.json()
    assert "token" not in data
    assert "student_name" not in data


def test_get_session_not_found(client):
    resp = client.get("/api/sessions/nonexistent")
    assert resp.status_code == 404
