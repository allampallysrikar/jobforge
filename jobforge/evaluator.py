"""
JobForge — Job Evaluator
Uses Gemini to score jobs against your profile and CV
"""

import json
from dataclasses import dataclass
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from .config import load_profile, load_cv, profile_to_text
from .gemini import generate, parse_json_response

console = Console()

GRADE_COLORS = {"A": "bold green", "B": "green", "C": "yellow", "D": "red", "F": "bold red"}
GRADE_EMOJI  = {"A": "🏆", "B": "✅", "C": "⚠️",  "D": "❌", "F": "🚫"}

EVAL_PROMPT = """You are an expert career advisor and recruiter with 20 years of experience.

Analyze this job description against the candidate's profile and CV. Provide a structured, honest evaluation.

═══════════════════════════════════════
CANDIDATE PROFILE:
{profile}

═══════════════════════════════════════
CANDIDATE CV:
{cv}

═══════════════════════════════════════
JOB DESCRIPTION:
{job_description}

═══════════════════════════════════════
SCORING WEIGHTS (use these exact weights):
{weights}

INSTRUCTIONS:
1. Score each dimension 1.0–5.0 (decimals allowed)
2. Apply the candidate's scoring weights to compute overall_score
3. Assign grade: A (4.5+), B (3.5-4.4), C (2.5-3.4), D (1.5-2.4), F (<1.5)
4. Be honest — if it's a poor fit, say so
5. Extract salary info if present, mark null if not mentioned

Return ONLY valid JSON, no markdown, no explanation:

{{
  "title": "extracted job title",
  "company": "extracted company name",
  "location": "extracted location",
  "remote_policy": "remote|hybrid|onsite|unclear",
  "salary_min": null_or_number,
  "salary_max": null_or_number,
  "salary_currency": "USD",
  "scores": {{
    "role_fit": 0.0,
    "salary_match": 0.0,
    "company_quality": 0.0,
    "growth_potential": 0.0,
    "tech_match": 0.0,
    "location_fit": 0.0,
    "culture_fit": 0.0
  }},
  "overall_score": 0.0,
  "grade": "A|B|C|D|F",
  "recommendation": "APPLY|MAYBE|SKIP",
  "one_line": "one sentence summary of fit",
  "strengths": ["why this is a good match — be specific"],
  "gaps": ["honest concerns or missing qualifications"],
  "tailoring_tips": ["specific CV/cover letter adjustments for this role"],
  "keywords": ["important keywords from JD to include in CV"],
  "interview_questions": ["likely questions they'll ask you"],
  "star_stories": ["which experiences from your CV to highlight and why"],
  "negotiation_notes": "salary negotiation advice for this specific role",
  "red_flags": ["any concerns about company or role"]
}}"""


@dataclass
class Evaluation:
    title: str
    company: str
    location: str
    remote_policy: str
    salary_min: float | None
    salary_max: float | None
    salary_currency: str
    scores: dict[str, float]
    overall_score: float
    grade: str
    recommendation: str
    one_line: str
    strengths: list[str]
    gaps: list[str]
    tailoring_tips: list[str]
    keywords: list[str]
    interview_questions: list[str]
    star_stories: list[str]
    negotiation_notes: str
    red_flags: list[str]
    raw: dict[str, Any]


def evaluate_job(job_description: str, verbose: bool = True) -> Evaluation:
    """
    Evaluate a job description against the user's profile and CV.
    Returns a structured Evaluation object.
    Retries automatically on rate-limit / transient errors.
    """
    profile = load_profile()
    cv      = load_cv()
    weights = profile.get("scoring_weights", {})

    prompt = EVAL_PROMPT.format(
        profile=profile_to_text(profile),
        cv=cv,
        job_description=job_description,
        weights=json.dumps(weights, indent=2),
    )

    if verbose:
        console.print("[dim]🤖 Analyzing job with Gemini…[/dim]")

    text = generate(prompt, label="evaluator")
    raw  = parse_json_response(text)

    eval_obj = Evaluation(
        title=raw.get("title", "Unknown Role"),
        company=raw.get("company", "Unknown Company"),
        location=raw.get("location", "Unknown"),
        remote_policy=raw.get("remote_policy", "unclear"),
        salary_min=raw.get("salary_min"),
        salary_max=raw.get("salary_max"),
        salary_currency=raw.get("salary_currency", "USD"),
        scores=raw.get("scores", {}),
        overall_score=float(raw.get("overall_score", 0)),
        grade=raw.get("grade", "F"),
        recommendation=raw.get("recommendation", "SKIP"),
        one_line=raw.get("one_line", ""),
        strengths=raw.get("strengths", []),
        gaps=raw.get("gaps", []),
        tailoring_tips=raw.get("tailoring_tips", []),
        keywords=raw.get("keywords", []),
        interview_questions=raw.get("interview_questions", []),
        star_stories=raw.get("star_stories", []),
        negotiation_notes=raw.get("negotiation_notes", ""),
        red_flags=raw.get("red_flags", []),
        raw=raw,
    )

    return eval_obj


def print_evaluation(ev: Evaluation) -> None:
    """Pretty-print an evaluation to the terminal."""
    grade_color = GRADE_COLORS.get(ev.grade, "white")
    grade_emoji = GRADE_EMOJI.get(ev.grade, "")

    # Header panel
    salary_str = "Not mentioned"
    if ev.salary_min or ev.salary_max:
        lo = f"${ev.salary_min:,.0f}" if ev.salary_min else "?"
        hi = f"${ev.salary_max:,.0f}" if ev.salary_max else "?"
        salary_str = f"{lo} – {hi} {ev.salary_currency}"

    header = (
        f"[bold]{ev.title}[/bold] @ [cyan]{ev.company}[/cyan]\n"
        f"[dim]{ev.location} · {ev.remote_policy} · {salary_str}[/dim]\n\n"
        f"[{grade_color}]{grade_emoji} Grade {ev.grade}  ·  {ev.overall_score:.1f}/5.0  ·  {ev.recommendation}[/{grade_color}]\n"
        f"[italic]{ev.one_line}[/italic]"
    )
    console.print(Panel(header, title="[bold blue]JobForge Evaluation[/bold blue]", border_style="blue"))

    # Scores table
    score_table = Table(box=box.SIMPLE, show_header=True, header_style="bold")
    score_table.add_column("Dimension", style="dim")
    score_table.add_column("Score", justify="right")
    score_table.add_column("Bar", width=20)

    for dim, score in ev.scores.items():
        bar_filled = int(score / 5.0 * 20)
        bar = "█" * bar_filled + "░" * (20 - bar_filled)
        color = "green" if score >= 4 else "yellow" if score >= 2.5 else "red"
        score_table.add_row(
            dim.replace("_", " ").title(),
            f"[{color}]{score:.1f}[/{color}]",
            f"[{color}]{bar}[/{color}]",
        )
    console.print(score_table)

    # Strengths
    if ev.strengths:
        console.print("\n[bold green]✓ Strengths[/bold green]")
        for s in ev.strengths:
            console.print(f"  [green]•[/green] {s}")

    # Gaps
    if ev.gaps:
        console.print("\n[bold red]✗ Gaps / Concerns[/bold red]")
        for g in ev.gaps:
            console.print(f"  [red]•[/red] {g}")

    # Red flags
    if ev.red_flags:
        console.print("\n[bold yellow]⚠ Red Flags[/bold yellow]")
        for rf in ev.red_flags:
            console.print(f"  [yellow]•[/yellow] {rf}")

    # Keywords
    if ev.keywords:
        kw_str = "  " + "  ".join(f"[cyan]{k}[/cyan]" for k in ev.keywords[:15])
        console.print(f"\n[bold]🏷 Keywords to include in CV:[/bold]\n{kw_str}")

    # Tailoring tips
    if ev.tailoring_tips:
        console.print("\n[bold blue]✏ CV Tailoring Tips[/bold blue]")
        for tip in ev.tailoring_tips:
            console.print(f"  [blue]→[/blue] {tip}")

    # Interview questions
    if ev.interview_questions:
        console.print("\n[bold magenta]🎤 Likely Interview Questions[/bold magenta]")
        for i, q in enumerate(ev.interview_questions[:5], 1):
            console.print(f"  [magenta]{i}.[/magenta] {q}")

    # Negotiation
    if ev.negotiation_notes:
        console.print(f"\n[bold]💰 Negotiation:[/bold] {ev.negotiation_notes}")

    console.print()


def evaluation_to_markdown(ev: Evaluation, url: str = "") -> str:
    """Convert evaluation to a markdown report."""
    salary_str = "Not mentioned"
    if ev.salary_min or ev.salary_max:
        lo = f"${ev.salary_min:,.0f}" if ev.salary_min else "?"
        hi = f"${ev.salary_max:,.0f}" if ev.salary_max else "?"
        salary_str = f"{lo} – {hi} {ev.salary_currency}"

    lines = [
        f"# Evaluation: {ev.title} @ {ev.company}",
        f"",
        f"**Grade:** {ev.grade}  **Score:** {ev.overall_score:.1f}/5.0  **Recommendation:** {ev.recommendation}",
        f"",
        f"> {ev.one_line}",
        f"",
        f"## Details",
        f"- **Location:** {ev.location} ({ev.remote_policy})",
        f"- **Salary:** {salary_str}",
    ]
    if url:
        lines.append(f"- **URL:** {url}")

    lines += [
        f"",
        f"## Scores",
        f"",
        f"| Dimension | Score |",
        f"|-----------|-------|",
    ]
    for dim, score in ev.scores.items():
        lines.append(f"| {dim.replace('_', ' ').title()} | {score:.1f}/5.0 |")

    if ev.strengths:
        lines += ["", "## Strengths", ""]
        for s in ev.strengths:
            lines.append(f"- {s}")

    if ev.gaps:
        lines += ["", "## Gaps / Concerns", ""]
        for g in ev.gaps:
            lines.append(f"- {g}")

    if ev.red_flags:
        lines += ["", "## ⚠ Red Flags", ""]
        for rf in ev.red_flags:
            lines.append(f"- {rf}")

    if ev.keywords:
        lines += ["", "## Keywords to Include in CV", ""]
        lines.append(", ".join(f"`{k}`" for k in ev.keywords))

    if ev.tailoring_tips:
        lines += ["", "## CV Tailoring Tips", ""]
        for tip in ev.tailoring_tips:
            lines.append(f"- {tip}")

    if ev.interview_questions:
        lines += ["", "## Likely Interview Questions", ""]
        for q in ev.interview_questions:
            lines.append(f"1. {q}")

    if ev.star_stories:
        lines += ["", "## STAR Stories to Highlight", ""]
        for story in ev.star_stories:
            lines.append(f"- {story}")

    if ev.negotiation_notes:
        lines += ["", "## Negotiation Notes", "", ev.negotiation_notes]

    lines += ["", "---", "*Generated by JobForge — https://github.com/allampallysrikar/jobforge*"]
    return "\n".join(lines)
