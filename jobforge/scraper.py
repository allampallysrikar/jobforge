"""
JobForge — Job Scraper
Fetches job descriptions from URLs using Playwright (handles JS-heavy sites).
Also scans company career pages for new listings via ATS APIs.
"""

import asyncio
import re
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

console = Console()

# ATS platform patterns
ATS_PATTERNS = {
    "greenhouse": r"greenhouse\.io|boards\.greenhouse\.io",
    "lever":      r"jobs\.lever\.co|lever\.co/",
    "ashby":      r"jobs\.ashbyhq\.com|ashbyhq\.com",
    "workday":    r"myworkdayjobs\.com|workday\.com",
    "icims":      r"icims\.com|careers\.\w+\.com/jobs",
    "taleo":      r"taleo\.net",
    "linkedin":   r"linkedin\.com/jobs",
    "indeed":     r"indeed\.com",
    "wellfound":  r"wellfound\.com|angel\.co",
}


def detect_ats(url: str) -> str | None:
    """Detect which ATS platform a URL belongs to."""
    for name, pattern in ATS_PATTERNS.items():
        if re.search(pattern, url, re.IGNORECASE):
            return name
    return None


# ─────────────────────────────────────────────────────────────
# Single Job Fetching
# ─────────────────────────────────────────────────────────────

async def _fetch_page_async(url: str) -> str:
    """Fetch a page using Playwright (handles JS rendering)."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = await context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            await page.wait_for_timeout(2_000)   # allow JS to render
            content = await page.content()
        finally:
            await browser.close()

    return content


def _extract_text(html: str, url: str = "") -> str:
    """Extract clean job description text from raw HTML."""
    soup = BeautifulSoup(html, "lxml")

    # Strip noise
    for tag in soup(["script", "style", "nav", "header", "footer",
                      "aside", "iframe", "noscript"]):
        tag.decompose()

    ats = detect_ats(url)

    # ATS-specific selectors for highest-quality extraction
    selectors: dict[str, list[str]] = {
        "greenhouse": ["#app", ".job-post", "[class*='job']"],
        "lever":      [".posting", ".content", "[class*='posting']"],
        "ashby":      ["[class*='job']", "main", "#content"],
        "workday":    ["[data-automation-id='jobPostingDescription']", "main"],
        "linkedin":   [".job-view-layout", ".description__text"],
        "wellfound":  [".job-description", "[class*='description']"],
    }

    if ats and ats in selectors:
        for sel in selectors[ats]:
            el = soup.select_one(sel)
            if el:
                return el.get_text(separator="\n", strip=True)

    # Generic: find the largest semantically-named element
    candidates = soup.find_all(
        ["main", "article", "section", "div"],
        class_=re.compile(r"job|posting|description|content|role", re.I),
    )
    if candidates:
        best = max(candidates, key=lambda x: len(x.get_text()))
        text = best.get_text(separator="\n", strip=True)
        if len(text) > 200:
            return text

    # Last resort: all body text
    body = soup.find("body")
    return (body or soup).get_text(separator="\n", strip=True)


def fetch_job_description(url: str) -> str:
    """
    Fetch and extract a job description from a URL.
    Uses Playwright so JavaScript-rendered pages work correctly.
    """
    console.print(f"[dim]🌐 Fetching: {url}[/dim]")
    html = asyncio.run(_fetch_page_async(url))
    text = _extract_text(html, url)

    # Collapse blank lines
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    cleaned = "\n".join(lines)

    if len(cleaned) < 100:
        raise ValueError(
            f"Could not extract job description from {url}. "
            "Try: jobforge eval --text   (paste the description directly)"
        )

    console.print(f"[dim]✓ Extracted {len(cleaned):,} characters[/dim]")
    return cleaned


# ─────────────────────────────────────────────────────────────
# Company Portal Scanning  (ATS APIs — no browser needed)
# ─────────────────────────────────────────────────────────────

async def _scan_greenhouse_async(
    company_slug: str, keywords: list[str], company_name: str
) -> list[dict]:
    """Scan a Greenhouse job board via the public API."""
    url = f"https://api.greenhouse.io/v1/boards/{company_slug}/jobs?content=true"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(url)
            r.raise_for_status()
            data = r.json()
    except Exception:
        return []

    jobs = []
    for job in data.get("jobs", []):
        title = job.get("title", "")
        if not keywords or any(kw.lower() in title.lower() for kw in keywords):
            jobs.append({
                "title": title,
                "url": job.get("absolute_url", ""),
                "location": ", ".join(
                    o.get("name", "") for o in job.get("offices", [])
                ),
                "source": "greenhouse",
                "company": company_name,
                "company_slug": company_slug,
            })
    return jobs


async def _scan_lever_async(
    company_slug: str, keywords: list[str], company_name: str
) -> list[dict]:
    """Scan a Lever job board via the public API."""
    url = f"https://api.lever.co/v0/postings/{company_slug}?mode=json"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(url)
            r.raise_for_status()
            data = r.json()
    except Exception:
        return []

    jobs = []
    for job in data:
        title = job.get("text", "")
        if not keywords or any(kw.lower() in title.lower() for kw in keywords):
            jobs.append({
                "title": title,
                "url": job.get("hostedUrl", ""),
                "location": job.get("categories", {}).get("location", ""),
                "source": "lever",
                "company": company_name,
                "company_slug": company_slug,
            })
    return jobs


async def _scan_ashby_async(
    company_slug: str, keywords: list[str], company_name: str
) -> list[dict]:
    """Scan an Ashby job board via their GraphQL API."""
    url = "https://jobs.ashbyhq.com/api/non-user-graphql"
    payload = {
        "operationName": "ApiJobBoardWithTeams",
        "variables": {"organizationHostedJobsPageName": company_slug},
        "query": (
            "query ApiJobBoardWithTeams($organizationHostedJobsPageName: String!) { "
            "jobBoard: jobBoardWithTeams(organizationHostedJobsPageName: $organizationHostedJobsPageName) { "
            "jobPostings { id title locationName jobUrl } } }"
        ),
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(url, json=payload)
            r.raise_for_status()
            data = r.json()
    except Exception:
        return []

    jobs = []
    postings = (
        (data.get("data") or {})
        .get("jobBoard", {})
        .get("jobPostings", [])
    )
    for job in postings:
        title = job.get("title", "")
        if not keywords or any(kw.lower() in title.lower() for kw in keywords):
            jobs.append({
                "title": title,
                "url": job.get("jobUrl", ""),
                "location": job.get("locationName", ""),
                "source": "ashby",
                "company": company_name,
                "company_slug": company_slug,
            })
    return jobs


async def scan_portals_async(portals_config: dict) -> list[dict]:
    """
    Scan ALL configured job portals concurrently.

    Runs every company in parallel — a 15-company scan takes the same
    time as one company rather than 15x as long.
    """
    companies = portals_config.get("companies", [])
    keywords  = portals_config.get("keywords", [])

    # Build coroutines
    coros: list[tuple[object, str]] = []
    for company in companies:
        ats  = company.get("ats", "").lower()
        slug = company.get("slug", "")
        name = company.get("name", slug)

        if ats == "greenhouse":
            coros.append((_scan_greenhouse_async(slug, keywords, name), name))
        elif ats == "lever":
            coros.append((_scan_lever_async(slug, keywords, name), name))
        elif ats == "ashby":
            coros.append((_scan_ashby_async(slug, keywords, name), name))
        else:
            console.print(f"[yellow]⚠ Unknown ATS '{ats}' for {name} — skipping[/yellow]")

    if not coros:
        return []

    all_jobs: list[dict] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task(
            f"[cyan]Scanning {len(coros)} companies…", total=len(coros)
        )

        # Run ALL scans concurrently — this is the key fix
        results = await asyncio.gather(
            *(coro for coro, _ in coros), return_exceptions=True
        )

        for (coro, company_name), result in zip(coros, results):
            progress.advance(task)
            if isinstance(result, Exception):
                console.print(f"[yellow]  ⚠ {company_name}: {result}[/yellow]")
            else:
                all_jobs.extend(result)

    return all_jobs


def scan_portals(portals_config: dict) -> list[dict]:
    """Synchronous wrapper for portal scanning."""
    return asyncio.run(scan_portals_async(portals_config))
