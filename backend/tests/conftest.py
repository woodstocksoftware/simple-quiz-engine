"""Shared fixtures for backend tests."""

from contextlib import asynccontextmanager
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@asynccontextmanager
async def _noop_lifespan(app):
    """Replacement lifespan that skips seeding — tests control their own data."""
    yield


@pytest.fixture()
def isolated_db(tmp_path):
    """Provide a fresh SQLite database in a temp directory for each test.

    Patches DATABASE_PATH before re-initialising the schema so every test
    gets a clean database with no leftover state.
    """
    db_path = tmp_path / "test.db"

    from app import database as db

    with patch.object(db, "DATABASE_PATH", db_path):
        db.init_database()
        yield db


@pytest.fixture()
def seed_quiz(isolated_db):
    """Seed the isolated DB with a test quiz and return the db module."""
    db = isolated_db
    db.create_quiz("test-quiz", "Test Quiz", 300, description="A test quiz")
    db.add_question("tq1", "test-quiz", 1, "What is 1+1?",
                    ["1", "2", "3", "4"], "2")
    db.add_question("tq2", "test-quiz", 2, "What is 2+2?",
                    ["2", "3", "4", "5"], "4")
    db.add_question("tq3", "test-quiz", 3, "What is 3+3?",
                    ["4", "5", "6", "7"], "6", points=2)
    return db


@pytest.fixture()
def client(isolated_db):
    """Provide a TestClient with the database patched to the isolated copy."""
    db = isolated_db

    from app import main

    with patch.object(main, "db", db), \
         patch.object(main.app.router, "lifespan_context", _noop_lifespan):
        main._rate_limit_store.clear()
        with TestClient(main.app) as tc:
            yield tc


@pytest.fixture()
def seeded_client(seed_quiz):
    """TestClient with a seeded quiz already in the database."""
    db = seed_quiz

    from app import main

    with patch.object(main, "db", db), \
         patch.object(main.app.router, "lifespan_context", _noop_lifespan):
        main._rate_limit_store.clear()
        with TestClient(main.app) as tc:
            yield tc
