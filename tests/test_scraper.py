"""
Tests for jobforge.scraper — ATS detection and text extraction.
These tests do NOT make real network calls or launch Playwright.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


# ── ATS detection ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("url,expected", [
    ("https://boards.greenhouse.io/anthropic/jobs/12345",  "greenhouse"),
    ("https://api.greenhouse.io/v1/boards/openai/jobs",    "greenhouse"),
    ("https://jobs.lever.co/vercel/abc123",                "lever"),
    ("https://jobs.ashbyhq.com/linear/role-id",            "ashby"),
    ("https://anthropic.com/careers",                      None),
    ("https://linkedin.com/jobs/view/12345",               "linkedin"),
    ("https://wellfound.com/jobs/1234-engineer",           "wellfound"),
    ("https://myworkdayjobs.com/company/job",              "workday"),
])
def test_detect_ats(url, expected):
    from jobforge.scraper import detect_ats
    assert detect_ats(url) == expected


# ── Text extraction ───────────────────────────────────────────────────────────

GREENHOUSE_HTML = """
<html>
<head><title>Senior Engineer</title></head>
<body>
  <nav>Nav stuff that should be removed</nav>
  <div id="app">
    <h1>Senior Software Engineer</h1>
    <p>We are looking for a Senior Software Engineer to join our team.</p>
    <h2>Requirements</h2>
    <ul>
      <li>5+ years Python</li>
      <li>Experience with distributed systems</li>
    </ul>
    <h2>Benefits</h2>
    <p>Great salary, remote-friendly</p>
  </div>
  <footer>Footer noise</footer>
</body>
</html>
"""

LEVER_HTML = """
<html>
<body>
  <header>Header</header>
  <div class="posting">
    <h2>Staff Engineer</h2>
    <div class="content">
      <p>Join us to build next-gen infrastructure.</p>
      <p>Requirements: 7+ years experience, Go or Rust preferred.</p>
    </div>
  </div>
</body>
</html>
"""


def test_extract_greenhouse_text():
    from jobforge.scraper import _extract_text
    text = _extract_text(GREENHOUSE_HTML, "https://boards.greenhouse.io/co/jobs/1")
    assert "Senior Software Engineer" in text
    assert "5+ years Python" in text
    # Nav/footer should be stripped
    assert "Nav stuff" not in text
    assert "Footer noise" not in text


def test_extract_lever_text():
    from jobforge.scraper import _extract_text
    text = _extract_text(LEVER_HTML, "https://jobs.lever.co/company/job-id")
    assert "Staff Engineer" in text
    assert "infrastructure" in text
    assert "Header" not in text


def test_extract_unknown_url_falls_back_to_body():
    html = "<html><body><main><p>ML Engineer role for an AI startup.</p></main></body></html>"
    from jobforge.scraper import _extract_text
    text = _extract_text(html, "https://unknown-ats.example.com/jobs/1")
    assert "ML Engineer" in text


# ── Greenhouse API scanner (mocked HTTP) ─────────────────────────────────────

@pytest.mark.asyncio
async def test_scan_greenhouse_filters_by_keyword():
    """Greenhouse scanner should only return jobs matching keywords."""
    import httpx
    from jobforge.scraper import _scan_greenhouse_async

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "jobs": [
            {"title": "Senior ML Engineer", "absolute_url": "https://boards.greenhouse.io/acme/jobs/1",
             "offices": [{"name": "Remote"}]},
            {"title": "Product Manager",     "absolute_url": "https://boards.greenhouse.io/acme/jobs/2",
             "offices": []},
            {"title": "Staff Engineer",      "absolute_url": "https://boards.greenhouse.io/acme/jobs/3",
             "offices": [{"name": "NYC"}]},
        ]
    }

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        results = await _scan_greenhouse_async("acme", ["Engineer"], "Acme Corp")

    titles = [r["title"] for r in results]
    assert "Senior ML Engineer" in titles
    assert "Staff Engineer" in titles
    assert "Product Manager" not in titles
    assert all(r["company"] == "Acme Corp" for r in results)


@pytest.mark.asyncio
async def test_scan_greenhouse_no_keywords_returns_all():
    import httpx
    from jobforge.scraper import _scan_greenhouse_async

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "jobs": [
            {"title": "SWE", "absolute_url": "https://x.com/1", "offices": []},
            {"title": "PM",  "absolute_url": "https://x.com/2", "offices": []},
        ]
    }

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        results = await _scan_greenhouse_async("co", [], "Co")

    assert len(results) == 2


@pytest.mark.asyncio
async def test_scan_greenhouse_handles_http_error():
    """A network error should return an empty list, not raise."""
    import httpx
    from jobforge.scraper import _scan_greenhouse_async

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("timeout"))
        mock_client_cls.return_value = mock_client

        results = await _scan_greenhouse_async("broken", ["Engineer"], "Broken Co")

    assert results == []


# ── Lever API scanner (mocked) ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_scan_lever_filters_by_keyword():
    from jobforge.scraper import _scan_lever_async

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = [
        {"text": "Backend Engineer", "hostedUrl": "https://jobs.lever.co/co/1",
         "categories": {"location": "Remote"}},
        {"text": "Designer",         "hostedUrl": "https://jobs.lever.co/co/2",
         "categories": {"location": "NYC"}},
    ]

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        results = await _scan_lever_async("co", ["Engineer"], "Co")

    assert len(results) == 1
    assert results[0]["title"] == "Backend Engineer"
