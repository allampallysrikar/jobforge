"""
JobForge — Configuration management
Loads user profile, CV, and app settings
"""

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from rich.console import Console

console = Console()

# Project root (where jobforge is run from)
ROOT = Path(os.getcwd())

# Paths
DATA_DIR    = ROOT / os.getenv("JOBFORGE_DATA_DIR", "data")
OUTPUT_DIR  = ROOT / os.getenv("JOBFORGE_OUTPUT_DIR", "output")
REPORTS_DIR = ROOT / os.getenv("JOBFORGE_REPORTS_DIR", "reports")
CONFIG_DIR  = ROOT / "config"
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

# DB path
DB_PATH = DATA_DIR / "jobforge.db"


def load_env() -> None:
    """Load .env file if present."""
    env_file = ROOT / ".env"
    if env_file.exists():
        load_dotenv(env_file)
    else:
        load_dotenv()  # try system env


def get_gemini_key() -> str:
    """Get Gemini API key from environment."""
    load_env()
    key = os.getenv("GEMINI_API_KEY", "")
    if not key or key == "your_gemini_api_key_here":
        console.print("[red]✗ GEMINI_API_KEY not set.[/red]")
        console.print("  Get a free key at: [link]https://aistudio.google.com/apikey[/link]")
        console.print("  Then add it to your .env file:")
        console.print("  [cyan]GEMINI_API_KEY=your_key_here[/cyan]")
        raise SystemExit(1)
    return key


def get_gemini_model() -> str:
    load_env()
    return os.getenv("GEMINI_MODEL", "gemini-2.5-flash-preview-05-20")


def load_profile() -> dict[str, Any]:
    """Load user profile from config/profile.yml."""
    profile_path = CONFIG_DIR / "profile.yml"
    if not profile_path.exists():
        example = CONFIG_DIR / "profile.example.yml"
        console.print(f"[red]✗ config/profile.yml not found.[/red]")
        console.print(f"  Copy the example and fill in your details:")
        console.print(f"  [cyan]cp config/profile.example.yml config/profile.yml[/cyan]")
        raise SystemExit(1)
    with open(profile_path) as f:
        return yaml.safe_load(f)


def load_cv() -> str:
    """Load user CV from cv.md."""
    cv_path = ROOT / "cv.md"
    if not cv_path.exists():
        console.print("[red]✗ cv.md not found.[/red]")
        console.print("  Create a cv.md file in the project root with your CV in markdown format.")
        console.print("  See docs/CV_GUIDE.md for tips on structuring your CV.")
        raise SystemExit(1)
    return cv_path.read_text()


def load_portals() -> dict[str, Any]:
    """Load job portal config from portals.yml."""
    portals_path = ROOT / "portals.yml"
    if not portals_path.exists():
        example = ROOT / "portals.example.yml"
        if example.exists():
            console.print("[yellow]⚠ portals.yml not found. Using portals.example.yml[/yellow]")
            with open(example) as f:
                return yaml.safe_load(f)
        return {"companies": [], "searches": []}
    with open(portals_path) as f:
        return yaml.safe_load(f)


def ensure_dirs() -> None:
    """Create data directories if they don't exist."""
    for d in [DATA_DIR, OUTPUT_DIR, REPORTS_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def profile_to_text(profile: dict[str, Any]) -> str:
    """Convert profile dict to readable text for AI prompts."""
    p = profile
    personal = p.get("personal", {})
    target = p.get("target", {})
    salary = p.get("salary", {})
    skills = p.get("skills", {})
    experience = p.get("experience", {})
    preferences = p.get("preferences", {})

    lines = [
        f"Name: {personal.get('name', 'N/A')}",
        f"Location: {personal.get('location', 'N/A')}",
        f"",
        f"TARGET ROLES:",
        f"  Titles: {', '.join(target.get('titles', []))}",
        f"  Domains: {', '.join(target.get('domains', []))}",
        f"  Remote preference: {target.get('remote_preference', 'any')}",
        f"",
        f"SALARY: ${salary.get('min_usd', 0):,} min, ${salary.get('target_usd', 0):,} target ({salary.get('currency', 'USD')})",
        f"",
        f"EXPERIENCE: {experience.get('years_total', 0)} years, {experience.get('level', 'mid')} level",
        f"  Highlights:",
    ]
    for h in experience.get("highlights", []):
        lines.append(f"    - {h}")

    lines += [
        f"",
        f"SKILLS:",
        f"  Languages: {', '.join(skills.get('languages', []))}",
        f"  Frameworks: {', '.join(skills.get('frameworks', []))}",
        f"  AI/ML: {', '.join(skills.get('ai_ml', []))}",
        f"  Infrastructure: {', '.join(skills.get('infrastructure', []))}",
        f"",
        f"PREFERENCES:",
        f"  Company size: {preferences.get('company_size', 'any')}",
        f"  Values: {', '.join(preferences.get('values', []))}",
        f"  Avoid: {', '.join(preferences.get('avoid', []))}",
        f"",
        f"SCORING WEIGHTS: {p.get('scoring_weights', {})}",
        f"DREAM COMPANIES: {', '.join(p.get('dream_companies', []))}",
        f"SKIP COMPANIES: {', '.join(p.get('skip_companies', []))}",
    ]
    return "\n".join(lines)
