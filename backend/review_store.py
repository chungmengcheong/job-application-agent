"""The one SQLite store module for durable `Review` records.

Opens a short-lived connection per call rather than holding one open — the
simplest safe option at personal scale, with no connection pooling.
"""
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from backend.db import get_db_path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ReviewRecord:
    id: str
    owner: str
    resume_content: str
    job_description: str
    source_url: str | None
    status: str
    created_at: str
    updated_at: str
    answers_json: list | None = None
    result_json: dict | None = None
    safe_error_code: str | None = None
    completed_at: str | None = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "ReviewRecord":
        return cls(
            id=row["id"],
            owner=row["owner"],
            resume_content=row["resume_content"],
            job_description=row["job_description"],
            source_url=row["source_url"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            answers_json=json.loads(row["answers_json"]) if row["answers_json"] else None,
            result_json=json.loads(row["result_json"]) if row["result_json"] else None,
            safe_error_code=row["safe_error_code"],
            completed_at=row["completed_at"],
        )


class ReviewStore:
    """Persists and retrieves `Review` records, scoped by owner."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self._db_path = str(db_path or get_db_path())

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def create(
        self,
        *,
        owner: str,
        resume_content: str,
        job_description: str,
        source_url: str | None,
    ) -> ReviewRecord:
        review_id = f"rev_{uuid4().hex}"
        now = _now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO reviews (
                    id, owner, resume_content, job_description, source_url,
                    status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'processing', ?, ?)
                """,
                (review_id, owner, resume_content, job_description, source_url, now, now),
            )
        return self.get(review_id)

    def get(self, review_id: str) -> ReviewRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM reviews WHERE id = ?", (review_id,)
            ).fetchone()
        return ReviewRecord.from_row(row) if row else None

    def get_for_owner(self, review_id: str, owner: str) -> ReviewRecord | None:
        record = self.get(review_id)
        if record is None or record.owner != owner:
            return None
        return record

    def _transition(
        self,
        review_id: str,
        status: str,
        *,
        result_json: dict | None = None,
        answers_json: list | None = None,
        safe_error_code: str | None = None,
        completed: bool = False,
    ) -> None:
        now = _now()
        # result_json/answers_json use COALESCE so a failure at Call 2 (or any
        # transition that doesn't pass a fresh value) never wipes out data a
        # prior successful transition already stored.
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE reviews
                SET status = ?,
                    result_json = COALESCE(?, result_json),
                    answers_json = COALESCE(?, answers_json),
                    safe_error_code = ?,
                    updated_at = ?,
                    completed_at = CASE WHEN ? THEN ? ELSE completed_at END
                WHERE id = ?
                """,
                (
                    status,
                    json.dumps(result_json) if result_json is not None else None,
                    json.dumps(answers_json) if answers_json is not None else None,
                    safe_error_code,
                    now,
                    completed,
                    now,
                    review_id,
                ),
            )

    def mark_awaiting_answers(self, review_id: str, result_json: dict) -> None:
        self._transition(review_id, "awaiting_answers", result_json=result_json)

    def mark_completed(self, review_id: str, result_json: dict, answers_json: list) -> None:
        self._transition(
            review_id,
            "completed",
            result_json=result_json,
            answers_json=answers_json,
            completed=True,
        )

    def mark_failed(
        self, review_id: str, safe_error_code: str, answers_json: list | None = None
    ) -> None:
        self._transition(
            review_id, "failed", answers_json=answers_json, safe_error_code=safe_error_code
        )
