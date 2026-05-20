"""
JobForge — PDF Generator
Renders HTML CV to a polished PDF using Playwright (free, no external service)
"""

import asyncio
from pathlib import Path
from datetime import datetime

from rich.console import Console

from .config import OUTPUT_DIR, ensure_dirs

console = Console()


def _safe_filename(company: str, title: str) -> str:
    """Generate a safe filename from company and title."""
    safe = lambda s: "".join(c if c.isalnum() or c in "- " else "" for c in s)
    c = safe(company).strip().replace(" ", "-")[:30]
    t = safe(title).strip().replace(" ", "-")[:30]
    date = datetime.now().strftime("%Y%m%d")
    return f"CV_{c}_{t}_{date}.pdf"


async def _render_pdf_async(html_content: str, output_path: Path) -> None:
    """Async PDF rendering with Playwright."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        # Load HTML directly
        await page.set_content(html_content, wait_until="networkidle")

        # Generate PDF with A4 settings
        await page.pdf(
            path=str(output_path),
            format="A4",
            margin={"top": "15mm", "bottom": "15mm", "left": "15mm", "right": "15mm"},
            print_background=True,
        )
        await browser.close()


def generate_pdf(html_content: str, company: str = "Company", title: str = "Role") -> Path:
    """
    Generate a PDF from HTML CV content.
    Returns the path to the generated PDF.
    """
    ensure_dirs()
    filename = _safe_filename(company, title)
    output_path = OUTPUT_DIR / filename

    console.print(f"[dim]📄 Rendering PDF...[/dim]")
    asyncio.run(_render_pdf_async(html_content, output_path))
    console.print(f"[green]✓ PDF saved:[/green] {output_path}")

    return output_path
