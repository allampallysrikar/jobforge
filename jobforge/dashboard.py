"""
JobForge — Terminal Dashboard
Rich-powered terminal UI to browse and manage your job pipeline
"""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text
from rich.prompt import Prompt, Confirm
from rich import box

from .tracker import (
    list_jobs, get_job, get_events, update_status,
    add_note, get_stats, STATUSES, STATUS_COLORS
)

console = Console()

GRADE_COLORS = {"A": "bold green", "B": "green", "C": "yellow", "D": "red", "F": "bold red"}
GRADE_EMOJI  = {"A": "🏆", "B": "✅", "C": "⚠️",  "D": "❌",  "F": "🚫"}


def _grade_text(grade: str | None) -> str:
    if not grade:
        return "[dim]—[/dim]"
    color = GRADE_COLORS.get(grade, "white")
    emoji = GRADE_EMOJI.get(grade, "")
    return f"[{color}]{emoji} {grade}[/{color}]"


def _score_bar(score: float | None, width: int = 10) -> str:
    if score is None:
        return "[dim]" + "─" * width + "[/dim]"
    filled = int((score / 5.0) * width)
    bar = "█" * filled + "░" * (width - filled)
    color = "green" if score >= 4 else "yellow" if score >= 2.5 else "red"
    return f"[{color}]{bar}[/{color}]"


def show_pipeline(
    status_filter: str | None = None,
    min_grade: str | None = None,
    company_filter: str | None = None,
) -> None:
    """Display the job pipeline as a rich table."""
    jobs = list_jobs(status=status_filter, min_grade=min_grade, company=company_filter)

    if not jobs:
        console.print("[dim]No jobs found with the current filters.[/dim]")
        return

    table = Table(
        title=f"[bold blue]JobForge Pipeline[/bold blue]  [dim]({len(jobs)} jobs)[/dim]",
        box=box.ROUNDED,
        show_lines=False,
        header_style="bold blue",
        border_style="blue",
    )
    table.add_column("#",       style="dim",    width=4,  justify="right")
    table.add_column("Grade",                   width=7,  justify="center")
    table.add_column("Score",                   width=12, justify="center")
    table.add_column("Title",   style="bold",   width=32)
    table.add_column("Company", style="cyan",   width=20)
    table.add_column("Status",                  width=14)
    table.add_column("Remote",  style="dim",    width=8)

    for job in jobs:
        status = job.get("status", "new")
        status_color = STATUS_COLORS.get(status, "white")
        remote = job.get("remote_policy", "")
        remote_display = {"remote": "🌍 yes", "hybrid": "🔀 hybrid", "onsite": "🏢 no"}.get(remote, "")

        table.add_row(
            str(job["id"]),
            _grade_text(job.get("grade")),
            _score_bar(job.get("overall_score")),
            job.get("title", "Unknown") or "Unknown",
            job.get("company", "Unknown") or "Unknown",
            f"[{status_color}]{status}[/{status_color}]",
            remote_display,
        )

    console.print(table)
    console.print(f"\n[dim]Commands: [cyan]jobforge status <id> <status>[/cyan] · "
                  f"[cyan]jobforge view <id>[/cyan] · [cyan]jobforge note <id>[/cyan][/dim]")


def show_job_detail(job_id: int) -> None:
    """Show detailed view of a single job."""
    job = get_job(job_id)
    if not job:
        console.print(f"[red]Job #{job_id} not found.[/red]")
        return

    import json
    eval_data = {}
    if job.get("evaluation_json"):
        try:
            eval_data = json.loads(job["evaluation_json"])
        except Exception:
            pass

    grade = job.get("grade", "?")
    grade_color = GRADE_COLORS.get(grade, "white")
    grade_emoji = GRADE_EMOJI.get(grade, "")

    salary_str = "Not mentioned"
    if job.get("salary_min") or job.get("salary_max"):
        lo = f"${job['salary_min']:,.0f}" if job.get("salary_min") else "?"
        hi = f"${job['salary_max']:,.0f}" if job.get("salary_max") else "?"
        salary_str = f"{lo} – {hi} {job.get('salary_currency', 'USD')}"

    header = (
        f"[bold]#{job_id}  {job.get('title', 'Unknown')}[/bold] @ [cyan]{job.get('company', 'Unknown')}[/cyan]\n"
        f"[dim]{job.get('location', '')} · {job.get('remote_policy', '')} · {salary_str}[/dim]\n\n"
        f"[{grade_color}]{grade_emoji} Grade {grade}  ·  {job.get('overall_score') or '—'}/5.0  ·  "
        f"{job.get('recommendation', '—')}[/{grade_color}]\n"
        f"[italic]{job.get('one_line', '')}[/italic]\n\n"
        f"Status: [{STATUS_COLORS.get(job.get('status', 'new'), 'white')}]{job.get('status', 'new')}[/]"
    )
    if job.get("url"):
        header += f"\n[link={job['url']}]🔗 {job['url']}[/link]"
    if job.get("cv_path"):
        header += f"\n📄 CV: {job['cv_path']}"

    console.print(Panel(header, title="[bold blue]Job Detail[/bold blue]", border_style="blue"))

    # Scores
    if eval_data.get("scores"):
        score_table = Table(box=box.SIMPLE, show_header=False)
        score_table.add_column("Dim", style="dim")
        score_table.add_column("Score", justify="right")
        score_table.add_column("Bar")
        for dim, score in eval_data["scores"].items():
            bar_w = int(float(score) / 5.0 * 15)
            bar = "█" * bar_w + "░" * (15 - bar_w)
            color = "green" if float(score) >= 4 else "yellow" if float(score) >= 2.5 else "red"
            score_table.add_row(
                dim.replace("_", " ").title(),
                f"[{color}]{float(score):.1f}[/{color}]",
                f"[{color}]{bar}[/{color}]",
            )
        console.print(score_table)

    # Strengths / Gaps
    panels = []
    if eval_data.get("strengths"):
        s_lines = "\n".join(f"[green]•[/green] {s}" for s in eval_data["strengths"])
        panels.append(Panel(s_lines, title="[green]Strengths[/green]", border_style="green"))
    if eval_data.get("gaps"):
        g_lines = "\n".join(f"[red]•[/red] {g}" for g in eval_data["gaps"])
        panels.append(Panel(g_lines, title="[red]Gaps[/red]", border_style="red"))
    if panels:
        console.print(Columns(panels))

    # Events timeline
    events = get_events(job_id)
    if events:
        console.print("\n[bold]📅 Timeline[/bold]")
        for ev in events:
            ts = ev["created_at"][:10] if ev.get("created_at") else ""
            color = STATUS_COLORS.get(ev["event_type"], "dim")
            console.print(f"  [dim]{ts}[/dim]  [{color}]{ev['event_type']}[/{color}]"
                          + (f"  [dim]{ev['notes']}[/dim]" if ev.get("notes") else ""))

    # Notes
    if job.get("notes"):
        console.print(f"\n[bold]📝 Notes[/bold]\n{job['notes']}")


def show_stats() -> None:
    """Display pipeline statistics."""
    stats = get_stats()

    # Summary panel
    total = stats["total"]
    avg = stats.get("avg_score")
    avg_str = f"{avg:.1f}/5.0" if avg else "—"

    console.print(Panel(
        f"[bold]{total}[/bold] jobs tracked  ·  avg score: [cyan]{avg_str}[/cyan]",
        title="[bold blue]JobForge Stats[/bold blue]",
        border_style="blue",
    ))

    # By status
    if stats["by_status"]:
        status_table = Table(title="By Status", box=box.SIMPLE, show_header=False)
        status_table.add_column("Status")
        status_table.add_column("Count", justify="right")
        for status in STATUSES:
            count = stats["by_status"].get(status, 0)
            if count:
                color = STATUS_COLORS.get(status, "white")
                status_table.add_row(f"[{color}]{status}[/{color}]", str(count))
        console.print(status_table)

    # By grade
    if stats["by_grade"]:
        grade_table = Table(title="By Grade", box=box.SIMPLE, show_header=False)
        grade_table.add_column("Grade")
        grade_table.add_column("Count", justify="right")
        for grade, count in sorted(stats["by_grade"].items()):
            color = GRADE_COLORS.get(grade, "white")
            grade_table.add_row(f"[{color}]{grade}[/{color}]", str(count))
        console.print(grade_table)
