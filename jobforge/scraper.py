"""
JobForge — Job Scraper
Fetches job descriptions from URLs using Playwright (handles JS-heavy sites)
Also scrapes company career pages for new listings
"""

import asyncio
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from rich.console import Console

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
    """Detect which ATS platform a URL is from."""
    for name, pattern in ATS_PATTERNS.items():
        if re.search(pattern, url, re.IGNORECASE):
            return name
    return None


async def _fetch_page_async(url: str) -> str:
    """Fetch a page using Playwright (handles JS rendering)."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )
        page = await context.new_page()

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            # Wait a bit for JS to render
            await page.wait_for_timeout(2000)
            content = await page.content()
        finally:
            await browser.close()

    return content


def _extract_text(html: str, url: str = "") -> str:
    """Extract clean job description text from HTML."""
    soup = BeautifulSoup(html, "lxml")

    # Remove noise elements
    for tag in soup(["script", "style", "nav", "header", "footer",
                      "aside", "iframe", "noscript", ".cookie-banner"]):
        tag.decompose()

    ats = detect_ats(url)

    # Try ATS-specific selectors first
    selectors = {
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

    # Generic fallback: find the largest text block
    candidates = soup.find_all(["main", "article", "section", "div"],
                                class_=re.compile(r"job|posting|description|content|role", re.I))
    if candidates:
        best = max(candidates, key=lambda x: len(x.get_text()))
        text = best.get_text(separator="\n", strip=True)
        if len(text) > 200:
            return text

    # Last resort: all body text
    body = soup.find("body")
    if body:
        return body.get_text(separator="\n", strip=True)

    return soup.get_text(separator="\n", strip=True)


def fetch_job_description(url: str) -> str:
    """
    Fetch and extract a job description from a URL.
    Handles JavaScript-rendered pages via Playwright.
    """
    console.print(f"[dim]🌐 Fetching: {url}[/dim]")
    html = asyncio.run(_fetch_page_async(url))
    text = _extract_text(html, url)

    # Clean up whitespace
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    cleaned = "\n".join(lines)

    if len(cleaned) < 100:
        raise ValueError(f"Could not extract job description from {url}. "
                         "Try pasting the description directly instead.")

    console.print(f"[dim]✓ Extracted {len(cleaned):,} characters[/dim]")
    return cleaned


# ─────────────────────────────────────────────────────────────
# Company Portal Scanner
# ─────────────────────────────────────────────────────────────

async def _scan_greenhouse_async(company_slug: str, keywords: list[str]) -> list[dict]:
    """Scan a Greenhouse job board."""
    import httpx
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
                "location": ", ".join(o.get("name", "") for o in job.get("offices", [])),
                "source": "greenhouse",
                "company_slug": company_slug,
            })
    return jobs


async def _scan_lever_async(company_slug: str, keywords: list[str]) -> list[dict]:
    """Scan a Lever job board."""
    import httpx
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
                "company_slug": company_slug,
            })
    return jobs


async def _scan_ashby_async(company_slug: str, keywords: list[str]) -> list[dict]:
    """Scan an Ashby job board."""
    import httpx
    url = f"https://jobs.ashbyhq.com/api/non-user-graphql"
    payload = {
        "operationName": "ApiJobBoardWithTeams",
        "variables": {"organizationHostedJobsPageName": company_slug},
        "query": "query ApiJobBoardWithTeams($organizationHostedJobsPageName: String!) { jobBoard: jobBoardWithTeams(organizationHostedJobsPageName: $organizationHostedJobsPageName) { jobPostings { id title locationName jobUrl } } }",
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(url, json=payload)
            r.raise_for_status()
            data = r.json()
    except Exception:
        return []

    jobs = []
    postings = (data.get("data") or {}).get("jobBoard", {}).get("jobPostings", [])
    for job in postings:
        title = job.get("title", "")
        if not keywords or any(kw.lower() in title.lower() for kw in keywords):
            jobs.append({
                "title": title,
                "url": job.get("jobUrl", ""),
                "location": job.get("locationName", ""),
                "source": "ashby",
                "company_slug": company_slug,
            })
    return jobs


async def scan_portals_async(portals_config: dict) -> list[dict]:
    """Scan all configured job portals for new listings."""
    companies = portals_config.get("companies", [])
    keywords = portals_config.get("keywords", [])
    all_jobs = []

    tasks = []
    for company in companies:
        ats = company.get("ats", "").lower()
        slug = company.get("slug", "")
        name = company.get("name", slug)

        if ats == "greenhouse":
            tasks.append((_scan_greenhouse_async(slug, keywords), name))
        elif ats == "lever":
            tasks.append((_scan_lever_async(slug, keywords), name))
        elif ats == "ashby":
            tasks.append((_scan_ashby_async(slug, keywords), name))

    for coro, company_name in tasks:
        try:
            jobs = await coro
            for j in jobs:
                j["company"] = company_name
            all_jobs.extend(jobs)
        except Exception as e:
            console.print(f"[yellow]⚠ Failed to scan {company_name}: {e}[/yellow]")

    return all_jobs


def scan_portals(portals_config: dict) -> list[dict]:
    """Synchronous wrapper for portal scanning."""
    return asyncio.run(scan_portals_async(portals_config))
