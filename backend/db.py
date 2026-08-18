"""SQLite schema and development-safe initialization for the `reviews` table.

No `users` or `resumes` tables and no foreign keys yet — that schema work is
Increment 3.5. `init_db()` only ever runs `CREATE ... IF NOT EXISTS`, so it is
safe to call on every process startup and never destroys existing data.
"""
import os
import sqlite3
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = REPO_ROOT / "data" / "reviews.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS reviews (
    id TEXT PRIMARY KEY,
    owner TEXT NOT NULL,
    resume_content TEXT NOT NULL,
    job_description TEXT NOT NULL,
    source_url TEXT,
    answers_json TEXT,
    result_json TEXT,
    status TEXT NOT NULL,
    safe_error_code TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_reviews_owner ON reviews(owner);
"""


def get_db_path() -> Path:
    """Return the configured reviews database path."""
    override = os.getenv("REVIEWS_DB_PATH")
    return Path(override) if override else DEFAULT_DB_PATH


def init_db(path: Path | None = None) -> Path:
    """Create the `reviews` table if it does not already exist."""
    db_path = path or get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA_SQL)
    return db_path


if __name__ == "__main__":
    initialized_path = init_db()
    print(f"Initialized reviews database at {initialized_path}")
