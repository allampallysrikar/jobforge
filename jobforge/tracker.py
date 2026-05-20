"""
JobForge — Application Tracker
SQLite-based database for tracking every job, evaluation, and application
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import DB_PATH, ensure_dirs

# Job status flow
STATUSES = [
    "new",          # just found, not evaluated
    "evaluated",    # scored by AI
    "shortlisted",  # you decided to apply
    "applied",      # application submitted
    "phone_screen", # phone/recruiter call
    "interview",    # technical / onsite interview
    "offer",        # received an offer
    "rejected",     # rejected at any stage
    "archived",     # decided not to pursue
]

STATUS_COLORS = {
    "new":          "dim",
    "evaluated":    "cyan",
    "shortlisted":  "blue",
    "applied":      "yellow",
    "phone_screen": "magenta",
    "interview":    "bright_magenta",
    "offer":        "bold green",
    "rejected":     "red",
    "archived":     "dim",
}


def _connect() -> sqlite3.Connection:
    ensure_dirs()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create database tables if they don't exist."""
    conn = _connect()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS jobs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            url             TEXT UNIQUE,
            title           TEXT,
            company         TEXT,
            location        TEXT,
            remote_policy   TEXT,
            salary_min      REAL,
            salary_max      REAL,
            salary_currency TEXT DEFAULT 'USD',
            status          TEXT DEFAULT 'new',
            grade           TEXT,
            overall_score   REAL,
            recommendation  TEXT,
            one_line        TEXT,
            evaluation_json TEXT,
            cv_path         TEXT,
            notes           TEXT,
            applied_at      TEXT,
            created_at      TEXT DEFAULT (datetime('now')),
            updated_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS events (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id     INTEGER REFERENCES jobs(id),
            event_type TEXT,
            notes      TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_jobs_status    ON jobs(status);
        CREATE INDEX IF NOT EXISTS idx_jobs_grade     ON jobs(grade);
        CREATE INDEX IF NOT EXISTS idx_jobs_company   ON jobs(company);
        CREATE INDEX IF NOT EXISTS idx_events_job_id  ON events(job_id);
    """)
    conn.commit()
    conn.close()


def add_job(url: str, title: str = "", company: str = "", location: str = "") -> int:
    """Add a new job to the tracker. Returns job ID."""
    init_db()
    conn = _connect()
    try:
        cur = conn.execute(
            """INSERT OR IGNORE INTO jobs (url, title, company, location)
               VALUES (?, ?, ?, ?)""",
            (url, title, company, location),
        )
        conn.commit()
        if cur.lastrowid:
            return cur.lastrowid
        # Already exists — return existing ID
        row = conn.execute("SELECT id FROM jobs WHERE url = ?", (url,)).fetchone()
        return row["id"]
    finally:
        conn.close()


def save_evaluation(job_id: int, evaluation: Any) -> None:
    """Save evaluation results to the database."""
    init_db()
    conn = _connect()
    try:
        conn.execute(
            """UPDATE jobs SET
                title           = ?,
                company         = ?,
                location        = ?,
                remote_policy   = ?,
                salary_min      = ?,
                salary_max      = ?,
                salary_currency = ?,
                grade           = ?,
                overall_score   = ?,
                recommendation  = ?,
                one_line        = ?,
                evaluation_json = ?,
                status          = 'evaluated',
                updated_at      = datetime('now')
               WHERE id = ?""",
            (
                evaluation.title,
                evaluation.company,
                evaluation.location,
                evaluation.remote_policy,
                evaluation.salary_min,
                evaluation.salary_max,
                evaluation.salary_currency,
                evaluation.grade,
                evaluation.overall_score,
                evaluation.recommendation,
                evaluation.one_line,
                json.dumps(evaluation.raw),
                job_id,
            ),
        )
        conn.execute(
            "INSERT INTO events (job_id, event_type, notes) VALUES (?, 'evaluated', ?)",
            (job_id, f"Grade {evaluation.grade} · {evaluation.overall_score:.1f}/5"),
        )
        conn.commit()
    finally:
        conn.close()


def save_cv_path(job_id: int, cv_path: str) -> None:
    """Save the path to a generated CV PDF."""
    init_db()
    conn = _connect()
    try:
        conn.execute(
            "UPDATE jobs SET cv_path = ?, updated_at = datetime('now') WHERE id = ?",
            (cv_path, job_id),
        )
        conn.commit()
    finally:
        conn.close()


def update_status(job_id: int, status: str, notes: str = "") -> None:
    """Update job status and log the event."""
    if status not in STATUSES:
        raise ValueError(f"Invalid status '{status}'. Choose from: {', '.join(STATUSES)}")
    init_db()
    conn = _connect()
    try:
        applied_at = datetime.now().isoformat() if status == "applied" else None
        if applied_at:
            conn.execute(
                "UPDATE jobs SET status = ?, applied_at = ?, updated_at = datetime('now') WHERE id = ?",
                (status, applied_at, job_id),
            )
        else:
            conn.execute(
                "UPDATE jobs SET status = ?, updated_at = datetime('now') WHERE id = ?",
                (status, job_id),
            )
        conn.execute(
            "INSERT INTO events (job_id, event_type, notes) VALUES (?, ?, ?)",
            (job_id, status, notes),
        )
        conn.commit()
    finally:
        conn.close()


def add_note(job_id: int, note: str) -> None:
    """Add a note to a job."""
    init_db()
    conn = _connect()
    try:
        conn.execute(
            "UPDATE jobs SET notes = COALESCE(notes || '\n', '') || ?, updated_at = datetime('now') WHERE id = ?",
            (note, job_id),
        )
        conn.execute(
            "INSERT INTO events (job_id, event_type, notes) VALUES (?, 'note', ?)",
            (job_id, note),
        )
        conn.commit()
    finally:
        conn.close()


def get_job(job_id: int) -> dict | None:
    """Get a single job by ID."""
    init_db()
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_job_by_url(url: str) -> dict | None:
    """Get a job by URL."""
    init_db()
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM jobs WHERE url = ?", (url,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_jobs(
    status: str | None = None,
    min_grade: str | None = None,
    company: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """List jobs with optional filters."""
    init_db()
    conn = _connect()
    try:
        grade_order = {"A": 5, "B": 4, "C": 3, "D": 2, "F": 1, None: 0}
        grade_filter_values = None
        if min_grade:
            grades = [g for g, v in grade_order.items() if v >= grade_order.get(min_grade, 0) and g]
            grade_filter_values = grades

        query = "SELECT * FROM jobs WHERE 1=1"
        params: list = []

        if status:
            query += " AND status = ?"
            params.append(status)
        if grade_filter_values:
            placeholders = ",".join("?" * len(grade_filter_values))
            query += f" AND grade IN ({placeholders})"
            params.extend(grade_filter_values)
        if company:
            query += " AND company LIKE ?"
            params.append(f"%{company}%")

        query += " ORDER BY overall_score DESC NULLS LAST, created_at DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_stats() -> dict:
    """Get pipeline statistics."""
    init_db()
    conn = _connect()
    try:
        total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        by_status = conn.execute(
            "SELECT status, COUNT(*) as cnt FROM jobs GROUP BY status"
        ).fetchall()
        by_grade = conn.execute(
            "SELECT grade, COUNT(*) as cnt FROM jobs WHERE grade IS NOT NULL GROUP BY grade ORDER BY grade"
        ).fetchall()
        avg_score = conn.execute(
            "SELECT AVG(overall_score) FROM jobs WHERE overall_score IS NOT NULL"
        ).fetchone()[0]
        return {
            "total": total,
            "by_status": {r["status"]: r["cnt"] for r in by_status},
            "by_grade": {r["grade"]: r["cnt"] for r in by_grade},
            "avg_score": round(avg_score, 2) if avg_score else None,
        }
    finally:
        conn.close()


def get_events(job_id: int) -> list[dict]:
    """Get all events for a job."""
    init_db()
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM events WHERE job_id = ? ORDER BY created_at ASC",
            (job_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
