"""
Tests for jobforge.config — profile loading, CV loading, path resolution.
"""

import os
import textwrap
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def patch_root(tmp_path, monkeypatch):
    """Point ROOT to a temp directory so tests never touch real user files."""
    monkeypatch.chdir(tmp_path)
    import jobforge.config as cfg
    monkeypatch.setattr(cfg, "ROOT",       tmp_path)
    monkeypatch.setattr(cfg, "CONFIG_DIR", tmp_path / "config")
    monkeypatch.setattr(cfg, "DATA_DIR",   tmp_path / "data")
    monkeypatch.setattr(cfg, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(cfg, "REPORTS_DIR",tmp_path / "reports")
    monkeypatch.setattr(cfg, "DB_PATH",    tmp_path / "data" / "jobforge.db")
    yield tmp_path


# ── profile loading ───────────────────────────────────────────────────────────

def test_load_profile_success(tmp_path):
    (tmp_path / "config").mkdir()
    profile_yml = textwrap.dedent("""\
        personal:
          name: Test User
          email: test@example.com
        target:
          titles:
            - Software Engineer
        scoring_weights:
          role_fit: 30
    """)
    (tmp_path / "config" / "profile.yml").write_text(profile_yml)

    from jobforge.config import load_profile
    profile = load_profile()
    assert profile["personal"]["name"] == "Test User"
    assert "Software Engineer" in profile["target"]["titles"]


def test_load_profile_missing_exits(tmp_path):
    from jobforge.config import load_profile
    with pytest.raises(SystemExit):
        load_profile()


# ── CV loading ────────────────────────────────────────────────────────────────

def test_load_cv_success(tmp_path):
    (tmp_path / "cv.md").write_text("# Jane Doe\n\nSenior Engineer with 5 years experience.")
    from jobforge.config import load_cv
    cv = load_cv()
    assert "Jane Doe" in cv


def test_load_cv_missing_exits(tmp_path):
    from jobforge.config import load_cv
    with pytest.raises(SystemExit):
        load_cv()


# ── portal loading ────────────────────────────────────────────────────────────

def test_load_portals_missing_returns_empty(tmp_path):
    from jobforge.config import load_portals
    portals = load_portals()
    # Either empty dict or falls back to example — both are acceptable
    assert isinstance(portals, dict)


def test_load_portals_success(tmp_path):
    portals_yml = textwrap.dedent("""\
        keywords:
          - Engineer
        companies:
          - name: Anthropic
            ats: greenhouse
            slug: anthropic
    """)
    (tmp_path / "portals.yml").write_text(portals_yml)
    from jobforge.config import load_portals
    portals = load_portals()
    assert len(portals["companies"]) == 1
    assert portals["companies"][0]["slug"] == "anthropic"


# ── profile_to_text ───────────────────────────────────────────────────────────

def test_profile_to_text_contains_key_fields():
    from jobforge.config import profile_to_text
    profile = {
        "personal": {"name": "Srikar", "location": "Hyderabad"},
        "target": {"titles": ["ML Engineer"], "domains": ["AI"], "remote_preference": "remote"},
        "salary": {"min_usd": 100_000, "target_usd": 150_000, "currency": "USD"},
        "skills": {"languages": ["Python"], "frameworks": ["FastAPI"], "ai_ml": [], "infrastructure": []},
        "experience": {"years_total": 3, "level": "mid", "highlights": ["Built X"]},
        "preferences": {"company_size": "startup", "values": ["impact"], "avoid": []},
        "scoring_weights": {},
        "dream_companies": ["Anthropic"],
        "skip_companies": [],
    }
    text = profile_to_text(profile)
    assert "Srikar" in text
    assert "ML Engineer" in text
    assert "Python" in text
    assert "Anthropic" in text


# ── ensure_dirs ───────────────────────────────────────────────────────────────

def test_ensure_dirs_creates_directories(tmp_path):
    from jobforge.config import ensure_dirs, DATA_DIR, OUTPUT_DIR, REPORTS_DIR
    ensure_dirs()
    assert DATA_DIR.exists()
    assert OUTPUT_DIR.exists()
    assert REPORTS_DIR.exists()
