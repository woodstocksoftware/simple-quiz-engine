"""Tests for the database layer (app/database.py)."""


# ── Quiz CRUD ──────────────────────────────────────────────


def test_create_and_get_quiz(isolated_db):
    db = isolated_db
    db.create_quiz("q1", "My Quiz", 600, description="desc")
    quiz = db.get_quiz("q1")
    assert quiz is not None
    assert quiz["title"] == "My Quiz"
    assert quiz["time_limit_seconds"] == 600
    assert quiz["description"] == "desc"


def test_get_quiz_not_found(isolated_db):
    assert isolated_db.get_quiz("nonexistent") is None


# ── Question CRUD ──────────────────────────────────────────


def test_add_and_get_questions(seed_quiz):
    db = seed_quiz
    questions = db.get_questions("test-quiz")
    assert len(questions) == 3
    assert questions[0]["question_text"] == "What is 1+1?"
    assert questions[0]["options"] == ["1", "2", "3", "4"]
    assert questions[0]["correct_answer"] == "2"


def test_get_questions_ordered(seed_quiz):
    db = seed_quiz
    questions = db.get_questions("test-quiz")
    numbers = [q["question_number"] for q in questions]
    assert numbers == [1, 2, 3]


def test_get_single_question(seed_quiz):
    db = seed_quiz
    q = db.get_question("tq1")
    assert q is not None
    assert q["correct_answer"] == "2"


def test_get_question_not_found(isolated_db):
    assert isolated_db.get_question("nonexistent") is None


def test_get_questions_for_client_excludes_correct_answer(seed_quiz):
    """Client-facing question data must never include correct_answer."""
    db = seed_quiz
    questions = db.get_questions_for_client("test-quiz")
    for q in questions:
        assert "correct_answer" not in q
    assert len(questions) == 3


# ── Session lifecycle ──────────────────────────────────────


def test_create_session(seed_quiz):
    db = seed_quiz
    session = db.create_session("s1", "test-quiz", "tok123", "Alice")
    assert session["status"] == "not_started"
    assert session["token"] == "tok123"
    assert session["time_remaining_seconds"] == 300


def test_start_session(seed_quiz):
    db = seed_quiz
    db.create_session("s1", "test-quiz", "tok", "Bob")
    result = db.start_session("s1")
    assert result["status"] == "in_progress"
    assert result["started_at"] is not None


def test_start_session_only_from_not_started(seed_quiz):
    db = seed_quiz
    db.create_session("s1", "test-quiz", "tok")
    db.start_session("s1")
    # Starting again should be a no-op (WHERE status = 'not_started')
    session = db.start_session("s1")
    assert session["status"] == "in_progress"


def test_complete_session(seed_quiz):
    db = seed_quiz
    db.create_session("s1", "test-quiz", "tok")
    db.start_session("s1")
    result = db.complete_session("s1", 85.0)
    assert result["status"] == "completed"
    assert result["score"] == 85.0
    assert result["completed_at"] is not None


def test_get_session_not_found(isolated_db):
    assert isolated_db.get_session("nonexistent") is None


# ── Response upsert ────────────────────────────────────────


def test_save_response_correct(seed_quiz):
    db = seed_quiz
    db.create_session("s1", "test-quiz", "tok")
    result = db.save_response("s1", "tq1", "2", 10)
    assert result["is_correct"] is True


def test_save_response_incorrect(seed_quiz):
    db = seed_quiz
    db.create_session("s1", "test-quiz", "tok")
    result = db.save_response("s1", "tq1", "3", 5)
    assert result["is_correct"] is False


def test_response_upsert_replaces_answer(seed_quiz):
    """Re-answering should update the answer and time_spent."""
    db = seed_quiz
    db.create_session("s1", "test-quiz", "tok")
    db.save_response("s1", "tq1", "3", 5)
    db.save_response("s1", "tq1", "2", 8)
    responses = db.get_responses("s1")
    assert len(responses) == 1
    assert responses[0]["answer"] == "2"
    assert responses[0]["time_spent_seconds"] == 8
    assert responses[0]["is_correct"] == 1


# ── Score calculation ──────────────────────────────────────


def test_calculate_score_perfect(seed_quiz):
    """All correct: 4 points earned out of 4 (q1=1, q2=1, q3=2)."""
    db = seed_quiz
    db.create_session("s1", "test-quiz", "tok")
    db.save_response("s1", "tq1", "2", 5)
    db.save_response("s1", "tq2", "4", 5)
    db.save_response("s1", "tq3", "6", 5)
    score = db.calculate_score("s1")
    assert score["earned"] == 4
    assert score["possible"] == 4
    assert score["correct"] == 3
    assert score["answered"] == 3
    assert score["total_questions"] == 3
    assert score["percentage"] == 100.0


def test_calculate_score_partial(seed_quiz):
    """One correct out of three, q1 worth 1 point, total possible 4."""
    db = seed_quiz
    db.create_session("s1", "test-quiz", "tok")
    db.save_response("s1", "tq1", "2", 5)   # correct (1pt)
    db.save_response("s1", "tq2", "2", 5)   # wrong
    db.save_response("s1", "tq3", "4", 5)   # wrong
    score = db.calculate_score("s1")
    assert score["earned"] == 1
    assert score["correct"] == 1
    assert score["percentage"] == 25.0


def test_calculate_score_no_answers(seed_quiz):
    """No answers submitted: 0% score."""
    db = seed_quiz
    db.create_session("s1", "test-quiz", "tok")
    score = db.calculate_score("s1")
    assert score["earned"] == 0
    assert score["percentage"] == 0.0
    assert score["answered"] == 0


def test_calculate_score_unanswered_counts_against(seed_quiz):
    """Only answering 1 of 3 questions — denominator is all quiz points."""
    db = seed_quiz
    db.create_session("s1", "test-quiz", "tok")
    db.save_response("s1", "tq1", "2", 5)  # correct (1pt)
    score = db.calculate_score("s1")
    assert score["earned"] == 1
    assert score["possible"] == 4
    assert score["percentage"] == 25.0


# ── Session time updates ─────────────────────────────────


def test_update_session_time(seed_quiz):
    """update_session_time persists the remaining time."""
    db = seed_quiz
    db.create_session("s1", "test-quiz", "tok")
    db.update_session_time("s1", 120)
    session = db.get_session("s1")
    assert session["time_remaining_seconds"] == 120


def test_update_current_question(seed_quiz):
    """update_current_question persists the question number."""
    db = seed_quiz
    db.create_session("s1", "test-quiz", "tok")
    db.update_current_question("s1", 3)
    session = db.get_session("s1")
    assert session["current_question"] == 3


# ── Error cases ───────────────────────────────────────────


def test_create_session_quiz_not_found(isolated_db):
    """Creating a session for a non-existent quiz raises ValueError."""
    import pytest
    with pytest.raises(ValueError, match="Quiz not found"):
        isolated_db.create_session("s1", "nonexistent-quiz", "tok")


# ── Seed data ─────────────────────────────────────────────


def test_seed_sample_quiz(isolated_db):
    """seed_sample_quiz creates the demo quiz with 5 questions."""
    db = isolated_db
    db.seed_sample_quiz()
    quiz = db.get_quiz("demo-quiz")
    assert quiz is not None
    assert quiz["title"] == "Python Fundamentals Quiz"
    assert quiz["time_limit_seconds"] == 300
    questions = db.get_questions("demo-quiz")
    assert len(questions) == 5


def test_seed_sample_quiz_idempotent(isolated_db):
    """Calling seed_sample_quiz twice doesn't create duplicates."""
    db = isolated_db
    db.seed_sample_quiz()
    db.seed_sample_quiz()
    questions = db.get_questions("demo-quiz")
    assert len(questions) == 5
