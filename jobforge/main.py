"""
JobForge — CLI Entry Point
Built by Srikar Allampally
"""

from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.panel import Panel

app = typer.Typer(
    name="jobforge",
    help="AI-powered job search automation — built by Srikar Allampally",
    add_completion=False,
    rich_markup_mode="rich",
)
console = Console()

BANNER = """[bold blue]
     ██╗ ██████╗ ██████╗ ███████╗ ██████╗ ██████╗  ██████╗ ███████╗
     ██║██╔═══██╗██╔══██╗██╔════╝██╔════╝██╔═══██╗██╔═══██╗██╔════╝
     ██║██║   ██║██████╔╝█████╗  ██║  ███╗██║   ██║██║   ██║█████╗
██   ██║██║   ██║██╔══██╗██╔══╝  ██║   ██║██║   ██║██║   ██║██╔══╝
╚█████╔╝╚██████╔╝██████╔╝██║     ╚██████╔╝╚██████╔╝╚██████╔╝███████╗
 ╚════╝  ╚═════╝ ╚═════╝ ╚═╝      ╚═════╝  ╚═════╝  ╚═════╝ ╚══════╝
[/bold blue][dim]   AI-powered job search automation · Built by Srikar Allampally[/dim]
"""


@app.command("eval")
def evaluate(
    url: Optional[str] = typer.Argument(None, help="Job posting URL"),
    text: bool = typer.Option(False, "--text", "-t", help="Paste job description instead of URL"),
    save: bool = typer.Option(True, "--save/--no-save", help="Save to tracker and reports"),
    pdf: bool = typer.Option(False, "--pdf", help="Also generate tailored CV PDF"),
):
    """
    Evaluate a job posting — scores it A–F against your CV and profile.

    Examples:
      jobforge eval https://jobs.ashbyhq.com/anthropic/senior-engineer
      jobforge eval --text
      jobforge eval <url> --pdf
    """
    from .evaluator import evaluate_job, print_evaluation, evaluation_to_markdown
    from .scraper import fetch_job_description
    from .config import REPORTS_DIR, ensure_dirs

    # Get job description
    if text or not url:
        console.print("[bold]Paste the job description below. Press Ctrl+D (or Ctrl+Z on Windows) when done:[/bold]")
        import sys
        job_description = sys.stdin.read().strip()
        url = url or "manual-input"
    else:
        job_description = fetch_job_description(url)

    # Evaluate
    evaluation = evaluate_job(job_description)
    print_evaluation(evaluation)

    if save:
        from .tracker import add_job, save_evaluation
        ensure_dirs()
        job_id = add_job(url=url, title=evaluation.title, company=evaluation.company)
        save_evaluation(job_id, evaluation)

        # Save report
        ensure_dirs()
        report_path = REPORTS_DIR / f"eval_{job_id}_{evaluation.company.replace(' ', '_')}.md"
        report_path.write_text(evaluation_to_markdown(evaluation, url=url))
        console.print(f"[dim]📋 Report saved: {report_path}[/dim]")
        console.print(f"[dim]🗄  Job #{job_id} added to tracker[/dim]")

        if pdf:
            _generate_pdf_for_job(job_id, job_description, evaluation)

        console.print(f"\n[dim]Next steps:[/dim]")
        console.print(f"  [cyan]jobforge view {job_id}[/cyan]      — view full details")
        console.print(f"  [cyan]jobforge cv {job_id}[/cyan]       — generate tailored CV PDF")
        console.print(f"  [cyan]jobforge status {job_id} shortlisted[/cyan] — mark as shortlisted")


@app.command("cv")
def generate_cv(
    job_id: int = typer.Argument(..., help="Job ID from tracker"),
    open_pdf: bool = typer.Option(False, "--open", help="Open PDF after generating"),
):
    """
    Generate a tailored ATS-optimized CV PDF for a specific job.

    Example:
      jobforge cv 42
    """
    from .tracker import get_job, save_cv_path
    from .evaluator import Evaluation
    from .cv_generator import generate_tailored_cv, render_cv_html
    from .pdf_gen import generate_pdf
    from .scraper import fetch_job_description
    import json

    job = get_job(job_id)
    if not job:
        console.print(f"[red]Job #{job_id} not found. Run [cyan]jobforge eval <url>[/cyan] first.[/red]")
        raise typer.Exit(1)

    # Reconstruct evaluation if available
    evaluation = None
    if job.get("evaluation_json"):
        try:
            raw = json.loads(job["evaluation_json"])
            from .evaluator import Evaluation
            evaluation = Evaluation(
                title=raw.get("title", ""),
                company=raw.get("company", ""),
                location=raw.get("location", ""),
                remote_policy=raw.get("remote_policy", ""),
                salary_min=raw.get("salary_min"),
                salary_max=raw.get("salary_max"),
                salary_currency=raw.get("salary_currency", "USD"),
                scores=raw.get("scores", {}),
                overall_score=float(raw.get("overall_score", 0)),
                grade=raw.get("grade", ""),
                recommendation=raw.get("recommendation", ""),
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
        except Exception:
            pass

    # Fetch job description for tailoring
    job_description = ""
    if job.get("url") and job["url"] != "manual-input":
        try:
            job_description = fetch_job_description(job["url"])
        except Exception:
            console.print("[yellow]⚠ Could not re-fetch job description. Using cached data.[/yellow]")

    _generate_pdf_for_job(job_id, job_description, evaluation)


def _generate_pdf_for_job(job_id: int, job_description: str, evaluation=None):
    from .cv_generator import generate_tailored_cv, render_cv_html
    from .pdf_gen import generate_pdf
    from .tracker import save_cv_path, get_job

    job = get_job(job_id)
    title = (job or {}).get("title", "Role")
    company = (job or {}).get("company", "Company")

    cv_data = generate_tailored_cv(
        job_description=job_description,
        evaluation=evaluation,
        job_title=title,
        company=company,
    )
    html = render_cv_html(cv_data)
    pdf_path = generate_pdf(html, company=company, title=title)
    save_cv_path(job_id, str(pdf_path))
    console.print(f"[green]✓ Tailored CV generated for {title} @ {company}[/green]")
    return pdf_path


@app.command("scan")
def scan(
    limit: int = typer.Option(50, "--limit", "-l", help="Max jobs to return"),
    auto_eval: bool = typer.Option(False, "--eval", help="Auto-evaluate all found jobs"),
):
    """
    Scan configured job portals for new listings.
    Configure companies in portals.yml.

    Example:
      jobforge scan
      jobforge scan --eval
    """
    from .scraper import scan_portals
    from .config import load_portals
    from .tracker import add_job, get_job_by_url

    console.print("[bold]🔍 Scanning job portals...[/bold]")
    portals = load_portals()
    jobs = scan_portals(portals)[:limit]

    if not jobs:
        console.print("[yellow]No new jobs found. Check your portals.yml configuration.[/yellow]")
        return

    new_count = 0
    for job in jobs:
        existing = get_job_by_url(job.get("url", ""))
        if not existing:
            add_job(
                url=job.get("url", ""),
                title=job.get("title", ""),
                company=job.get("company", ""),
                location=job.get("location", ""),
            )
            new_count += 1
            console.print(f"  [green]+[/green] {job['company']} — {job['title']}")
        else:
            console.print(f"  [dim]~[/dim] {job.get('company', '')} — {job.get('title', '')} [dim](already tracked)[/dim]")

    console.print(f"\n[bold green]✓ Found {len(jobs)} jobs ({new_count} new)[/bold green]")

    if auto_eval:
        console.print("\n[bold]🤖 Auto-evaluating new jobs...[/bold]")
        from .tracker import list_jobs
        new_jobs = list_jobs(status="new")
        for job in new_jobs[:10]:  # Limit to avoid API rate limits
            if job.get("url") and job["url"] != "manual-input":
                console.print(f"\n[dim]Evaluating: {job['title']} @ {job['company']}...[/dim]")
                try:
                    from .scraper import fetch_job_description
                    from .evaluator import evaluate_job
                    from .tracker import save_evaluation
                    jd = fetch_job_description(job["url"])
                    ev = evaluate_job(jd, verbose=False)
                    save_evaluation(job["id"], ev)
                    from .evaluator import GRADE_COLORS, GRADE_EMOJI
                    color = GRADE_COLORS.get(ev.grade, "white")
                    emoji = GRADE_EMOJI.get(ev.grade, "")
                    console.print(f"  [{color}]{emoji} {ev.grade}  {ev.overall_score:.1f}/5[/{color}]  {ev.title} @ {ev.company}")
                except Exception as e:
                    console.print(f"  [red]Failed: {e}[/red]")

    console.print(f"\n[dim]View pipeline: [cyan]jobforge pipeline[/cyan][/dim]")


@app.command("pipeline")
def pipeline(
    status: Optional[str] = typer.Option(None, "--status", "-s", help="Filter by status"),
    grade: Optional[str] = typer.Option(None, "--grade", "-g", help="Minimum grade (A/B/C/D/F)"),
    company: Optional[str] = typer.Option(None, "--company", "-c", help="Filter by company name"),
):
    """
    View your job application pipeline.

    Examples:
      jobforge pipeline
      jobforge pipeline --grade B
      jobforge pipeline --status applied
    """
    from .dashboard import show_pipeline
    show_pipeline(status_filter=status, min_grade=grade, company_filter=company)


@app.command("view")
def view(job_id: int = typer.Argument(..., help="Job ID")):
    """
    View detailed information about a specific job.

    Example:
      jobforge view 42
    """
    from .dashboard import show_job_detail
    show_job_detail(job_id)


@app.command("status")
def set_status(
    job_id: int = typer.Argument(..., help="Job ID"),
    new_status: str = typer.Argument(..., help="New status"),
    note: str = typer.Option("", "--note", "-n", help="Optional note"),
):
    """
    Update the status of a job in your pipeline.

    Valid statuses: new, evaluated, shortlisted, applied, phone_screen,
                    interview, offer, rejected, archived

    Example:
      jobforge status 42 applied
      jobforge status 42 interview --note "Technical round scheduled for Friday"
    """
    from .tracker import update_status, STATUSES
    if new_status not in STATUSES:
        console.print(f"[red]Invalid status '{new_status}'.[/red]")
        console.print(f"Valid statuses: {', '.join(STATUSES)}")
        raise typer.Exit(1)
    update_status(job_id, new_status, notes=note)
    console.print(f"[green]✓ Job #{job_id} status updated to '{new_status}'[/green]")


@app.command("note")
def add_note_cmd(
    job_id: int = typer.Argument(..., help="Job ID"),
    note: Optional[str] = typer.Argument(None, help="Note text"),
):
    """
    Add a note to a job.

    Example:
      jobforge note 42 "Recruiter was very responsive"
    """
    from .tracker import add_note
    if not note:
        note = typer.prompt("Note")
    add_note(job_id, note)
    console.print(f"[green]✓ Note added to job #{job_id}[/green]")


@app.command("search")
def search(
    query: str = typer.Argument(..., help="Search text (title, company, or location)"),
    grade: Optional[str] = typer.Option(None, "--grade", "-g", help="Minimum grade filter"),
):
    """
    Search jobs in your tracker by title, company, or location.

    Example:
      jobforge search "staff engineer"
      jobforge search anthropic --grade B
    """
    from .tracker import list_jobs
    from .dashboard import show_pipeline

    jobs = list_jobs(min_grade=grade, limit=200)
    q = query.lower()
    matched = [
        j for j in jobs
        if q in (j.get("title") or "").lower()
        or q in (j.get("company") or "").lower()
        or q in (j.get("location") or "").lower()
    ]

    if not matched:
        console.print(f"[yellow]No jobs matching '[bold]{query}[/bold]'[/yellow]")
        return

    console.print(f"[dim]Found [bold]{len(matched)}[/bold] jobs matching '{query}'[/dim]\n")
    # Re-use the pipeline view by temporarily replacing list_jobs
    from .dashboard import show_pipeline
    from . import dashboard as _dash
    _orig = _dash.list_jobs
    _dash.list_jobs = lambda **kw: matched   # monkey-patch for this call
    show_pipeline()
    _dash.list_jobs = _orig


@app.command("open")
def open_job(
    job_id: int = typer.Argument(..., help="Job ID to open in browser"),
):
    """
    Open a job URL in your default browser.

    Example:
      jobforge open 42
    """
    import webbrowser
    from .tracker import get_job

    job = get_job(job_id)
    if not job:
        console.print(f"[red]Job #{job_id} not found.[/red]")
        raise typer.Exit(1)

    url = job.get("url", "")
    if not url or url == "manual-input":
        console.print(f"[yellow]Job #{job_id} has no URL.[/yellow]")
        raise typer.Exit(1)

    console.print(f"[dim]Opening:[/dim] {url}")
    webbrowser.open(url)


@app.command("export")
def export(
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path (default: pipeline.csv)"),
    status: Optional[str] = typer.Option(None, "--status", "-s", help="Filter by status"),
    grade: Optional[str] = typer.Option(None, "--grade", "-g", help="Minimum grade"),
    fmt: str = typer.Option("csv", "--format", "-f", help="Output format: csv or json"),
):
    """
    Export your job pipeline to CSV or JSON.

    Examples:
      jobforge export
      jobforge export --format json --output jobs.json
      jobforge export --status applied --grade B
    """
    import csv
    import json as _json
    from pathlib import Path
    from .tracker import list_jobs

    jobs = list_jobs(status=status, min_grade=grade, limit=1000)
    if not jobs:
        console.print("[yellow]No jobs to export.[/yellow]")
        return

    default_name = f"pipeline.{fmt}"
    out_path = Path(output or default_name)

    if fmt == "json":
        # Remove raw evaluation JSON to keep the export readable
        clean = [{k: v for k, v in j.items() if k != "evaluation_json"} for j in jobs]
        out_path.write_text(_json.dumps(clean, indent=2))
    else:
        # CSV
        cols = [
            "id", "title", "company", "location", "remote_policy",
            "grade", "overall_score", "recommendation", "status",
            "salary_min", "salary_max", "salary_currency",
            "applied_at", "cv_path", "url", "created_at",
        ]
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(jobs)

    console.print(f"[green]✓ Exported {len(jobs)} jobs → {out_path}[/green]")


@app.command("stats")
def stats():
    """Show pipeline statistics and summary."""
    from .dashboard import show_stats
    show_stats()


@app.command("doctor")
def doctor():
    """
    Check that everything is set up correctly.
    Run this first after installing JobForge.
    """
    import shutil
    from .config import ROOT

    console.print(Panel("[bold]JobForge — Setup Check[/bold]", border_style="blue"))
    ok = True

    # Python version
    import sys
    py = sys.version_info
    if py >= (3, 11):
        console.print(f"[green]✓[/green] Python {py.major}.{py.minor}.{py.micro}")
    else:
        console.print(f"[red]✗ Python {py.major}.{py.minor} — need 3.11+[/red]")
        ok = False

    # Gemini API key
    import os
    from dotenv import load_dotenv
    load_dotenv()
    key = os.getenv("GEMINI_API_KEY", "")
    if key and key != "your_gemini_api_key_here":
        console.print(f"[green]✓[/green] GEMINI_API_KEY is set")
    else:
        console.print(f"[red]✗ GEMINI_API_KEY not set[/red]")
        console.print(f"  Get a FREE key at: [link]https://aistudio.google.com/apikey[/link]")
        console.print(f"  Add to .env: [cyan]GEMINI_API_KEY=your_key_here[/cyan]")
        ok = False

    # profile.yml
    profile_path = ROOT / "config" / "profile.yml"
    if profile_path.exists():
        console.print(f"[green]✓[/green] config/profile.yml found")
    else:
        console.print(f"[yellow]⚠ config/profile.yml not found[/yellow]")
        console.print(f"  [cyan]cp config/profile.example.yml config/profile.yml[/cyan]")
        ok = False

    # cv.md
    cv_path = ROOT / "cv.md"
    if cv_path.exists():
        console.print(f"[green]✓[/green] cv.md found ({cv_path.stat().st_size} bytes)")
    else:
        console.print(f"[yellow]⚠ cv.md not found[/yellow]")
        console.print(f"  Create cv.md with your CV in markdown format")
        ok = False

    # Playwright
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
        console.print(f"[green]✓[/green] Playwright + Chromium working")
    except Exception as e:
        console.print(f"[red]✗ Playwright not working: {e}[/red]")
        console.print(f"  Run: [cyan]playwright install chromium[/cyan]")
        ok = False

    # Gemini connectivity test
    if key and key != "your_gemini_api_key_here":
        try:
            import google.generativeai as genai
            genai.configure(api_key=key)
            model = genai.GenerativeModel(os.getenv("GEMINI_MODEL", "gemini-2.5-flash-preview-05-20"))
            r = model.generate_content("Say 'OK' in one word.")
            console.print(f"[green]✓[/green] Gemini API connection working")
        except Exception as e:
            console.print(f"[red]✗ Gemini API error: {e}[/red]")
            ok = False

    console.print()
    if ok:
        console.print("[bold green]✓ Everything looks good! You're ready to use JobForge.[/bold green]")
        console.print("\n[bold]Quick start:[/bold]")
        console.print("  [cyan]jobforge eval https://jobs.ashbyhq.com/anthropic/...[/cyan]")
        console.print("  [cyan]jobforge scan[/cyan]")
        console.print("  [cyan]jobforge pipeline[/cyan]")
    else:
        console.print("[bold yellow]⚠ Fix the issues above before using JobForge.[/bold yellow]")


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """JobForge — AI-powered job search automation."""
    if ctx.invoked_subcommand is None:
        console.print(BANNER)
        console.print("[bold]Commands:[/bold]")
        commands = [
            ("eval <url>",       "Evaluate a job posting (scores A–F)"),
            ("eval --text",      "Evaluate by pasting job description"),
            ("cv <job_id>",      "Generate tailored CV PDF"),
            ("scan",             "Scan job portals for new listings"),
            ("pipeline",         "View your application pipeline"),
            ("search <query>",   "Search jobs by title, company, location"),
            ("view <job_id>",    "View job details"),
            ("open <job_id>",    "Open job URL in browser"),
            ("status <id> <s>",  "Update job status"),
            ("note <job_id>",    "Add a note to a job"),
            ("export",           "Export pipeline to CSV or JSON"),
            ("stats",            "Pipeline statistics"),
            ("doctor",           "Check setup"),
        ]
        for cmd, desc in commands:
            console.print(f"  [cyan]jobforge {cmd:<22}[/cyan] {desc}")
        console.print()
        console.print("[dim]Run [cyan]jobforge doctor[/cyan] to check your setup.[/dim]")


if __name__ == "__main__":
    app()
