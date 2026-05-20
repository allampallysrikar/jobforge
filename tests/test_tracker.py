"""
Tests for jobforge.tracker — SQLite-backed application tracker.
Uses a temporary database so tests never touch the real data/jobforge.db.
"""

import json
import os
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    """Redirect every DB operation to a fresh temp file for each test."""
    db = tmp_path / "test.db"
    # Patch the module-level constants BEFORE any import reaches them
    monkeypatch.setenv("JOBFORGE_DATA_DIR", str(tmp_path))
    import jobforge.config as cfg
    monkeypatch.setattr(cfg, "DATA_DIR", tmp_path)
    monkeypatch.setattr(cfg, "DB_PATH",  db)
    import jobforge.tracker as tracker
    monkeypatch.setattr(tracker, "DB_PATH", db)
    yield db


# ── add_job ───────────────────────────────────────────────────────────────────

def test_add_job_returns_id():
    from jobforge.tracker import add_job
    job_id = add_job(url="https://example.com/job/1", title="SWE", company="Acme")
    assert isinstance(job_id, int)
    assert job_id > 0


def test_add_job_dedup_by_url():
    """Adding the same URL twice should return the same ID."""
    from jobforge.tracker import add_job
    id1 = add_job(url="https://example.com/job/dup", title="A", company="A")
    id2 = add_job(url="https://example.com/job/dup", title="B", company="B")
    assert id1 == id2


def test_add_job_different_urls():
    from jobforge.tracker import add_job
    id1 = add_job(url="https://example.com/job/1")
    id2 = add_job(url="https://example.com/job/2")
    assert id1 != id2


# ── get_job / get_job_by_url ───────────────────────────────────────────────────

def test_get_job_returns_dict():
    from jobforge.tracker import add_job, get_job
    job_id = add_job(url="https://example.com/job/g1", title="ML Eng", company="Cohere")
    job = get_job(job_id)
    assert job is not None
    assert job["title"] == "ML Eng"
    assert job["company"] == "Cohere"


def test_get_job_missing_returns_none():
    from jobforge.tracker import get_job
    assert get_job(99999) is None


def test_get_job_by_url():
    from jobforge.tracker import add_job, get_job_by_url
    add_job(url="https://example.com/job/byurl", title="T", company="C")
    job = get_job_by_url("https://example.com/job/byurl")
    assert job is not None
    assert job["title"] == "T"


def test_get_job_by_url_missing_returns_none():
    from jobforge.tracker import get_job_by_url
    assert get_job_by_url("https://doesnotexist.example.com") is None


# ── update_status ─────────────────────────────────────────────────────────────

def test_update_status_valid():
    from jobforge.tracker import add_job, update_status, get_job
    job_id = add_job(url="https://example.com/job/s1")
    update_status(job_id, "applied")
    job = get_job(job_id)
    assert job["status"] == "applied"


def test_update_status_applied_sets_applied_at():
    from jobforge.tracker import add_job, update_status, get_job
    job_id = add_job(url="https://example.com/job/s2")
    update_status(job_id, "applied")
    job = get_job(job_id)
    assert job["applied_at"] is not None


def test_update_status_invalid_raises():
    from jobforge.tracker import add_job, update_status
    job_id = add_job(url="https://example.com/job/s3")
    with pytest.raises(ValueError, match="Invalid status"):
        update_status(job_id, "hired")


# ── add_note ──────────────────────────────────────────────────────────────────

def test_add_note_appends():
    from jobforge.tracker import add_job, add_note, get_job
    job_id = add_job(url="https://example.com/job/n1")
    add_note(job_id, "First note")
    add_note(job_id, "Second note")
    job = get_job(job_id)
    assert "First note" in job["notes"]
    assert "Second note" in job["notes"]


# ── list_jobs ─────────────────────────────────────────────────────────────────

def test_list_jobs_returns_all():
    from jobforge.tracker import add_job, list_jobs
    add_job(url="https://example.com/job/l1")
    add_job(url="https://example.com/job/l2")
    jobs = list_jobs()
    assert len(jobs) >= 2


def test_list_jobs_status_filter():
    from jobforge.tracker import add_job, update_status, list_jobs
    id1 = add_job(url="https://example.com/job/f1")
    id2 = add_job(url="https://example.com/job/f2")
    update_status(id1, "applied")
    applied = list_jobs(status="applied")
    ids = [j["id"] for j in applied]
    assert id1 in ids
    assert id2 not in ids


# ── get_stats ─────────────────────────────────────────────────────────────────

def test_get_stats_empty_db():
    from jobforge.tracker import get_stats
    stats = get_stats()
    assert stats["total"] == 0
    assert stats["avg_score"] is None


def test_get_stats_counts():
    from jobforge.tracker import add_job, update_status, get_stats
    add_job(url="https://example.com/job/st1")
    id2 = add_job(url="https://example.com/job/st2")
    update_status(id2, "applied")
    stats = get_stats()
    assert stats["total"] == 2
    assert stats["by_status"].get("applied", 0) == 1


# ── get_events ────────────────────────────────────────────────────────────────

def test_events_created_on_status_change():
    from jobforge.tracker import add_job, update_status, get_events
    job_id = add_job(url="https://example.com/job/ev1")
    update_status(job_id, "applied", notes="sent!")
    events = get_events(job_id)
    assert any(e["event_type"] == "applied" for e in events)
