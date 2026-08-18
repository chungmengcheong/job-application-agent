"""Tests for the development-safe reviews database initialization."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from backend import db


def test_init_db_creates_reviews_table(tmp_path: Path) -> None:
    db_path = tmp_path / "reviews.db"

    db.init_db(db_path)

    with sqlite3.connect(db_path) as conn:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    assert "reviews" in tables


def test_init_db_creates_parent_directory(tmp_path: Path) -> None:
    db_path = tmp_path / "nested" / "reviews.db"

    db.init_db(db_path)

    assert db_path.exists()


def test_init_db_is_idempotent_and_preserves_data(tmp_path: Path) -> None:
    db_path = tmp_path / "reviews.db"
    db.init_db(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO reviews (
                id, owner, resume_content, job_description, status,
                created_at, updated_at
            ) VALUES ('rev_1', 'owner', 'resume', 'jd', 'processing', 't', 't')
            """
        )

    db.init_db(db_path)

    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT id FROM reviews WHERE id = 'rev_1'").fetchone()
    assert row is not None


def test_get_db_path_honors_env_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    override = tmp_path / "custom" / "reviews.db"
    monkeypatch.setenv("REVIEWS_DB_PATH", str(override))

    assert db.get_db_path() == override


def test_get_db_path_defaults_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REVIEWS_DB_PATH", raising=False)

    assert db.get_db_path() == db.DEFAULT_DB_PATH
