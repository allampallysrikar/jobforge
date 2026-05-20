# Changelog

All notable changes to JobForge are documented here.  
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [1.0.0] — 2026-05-20

First public release.

### Added

**Core application**
- `jobforge eval <url>` — AI job evaluation: scores a posting A–F across 7 weighted dimensions (role fit, salary, growth, culture, skills, location, company health) using Gemini 2.5 Flash
- `jobforge eval --text` — evaluate by pasting a job description directly
- `jobforge eval <url> --pdf` — evaluate and generate a tailored CV PDF in one step
- `jobforge cv <job_id>` — generate a tailored CV PDF for any tracked job
- `jobforge scan` — concurrent scan of configured job portals (Greenhouse, Lever, Ashby)
- `jobforge scan --eval` — scan + auto-evaluate all newly discovered jobs (targets only new IDs, not the full database)
- `jobforge scan --eval --max-eval N` — cap the number of jobs auto-evaluated per scan run
- `jobforge pipeline` — Rich terminal table of your full application pipeline
- `jobforge pipeline --grade B` — filter by minimum grade
- `jobforge pipeline --status applied` — filter by status
- `jobforge view <job_id>` — view the stored evaluation report for a job
- `jobforge status <id> <status>` — update a job's application status
- `jobforge note <id> "text"` — attach a note to any job
- `jobforge search <query>` — search jobs by title, company, or location
- `jobforge open <job_id>` — open a job's URL in the default browser
- `jobforge export` — export the pipeline to CSV or JSON (`--format`, `--output`, `--status`, `--grade`)
- `jobforge stats` — pipeline statistics: totals by status, grade distribution, success rate
- `jobforge doctor` — environment check: Python version, Gemini key, Playwright, config files

**Infrastructure**
- SQLite job tracker (`data/jobforge.db`) — zero-setup, zero-config persistence
- Event log: every status change and note is recorded with a timestamp
- `jobforge.gemini` module — shared `generate()` wrapper with exponential backoff (handles Gemini 429 rate-limit and 5xx transient errors), plus `parse_json_response()` with JSON-fence stripping and regex fallback
- `asyncio.gather()` fan-out in the portal scanner — all company ATS endpoints queried concurrently, not sequentially
- Rich progress bar (spinner + bar + task count) during portal scan
- Playwright headless browser for JS-rendered job pages and HTML→PDF rendering
- Jinja2 HTML CV template (`templates/cv.html`) rendered to PDF via Playwright

**Config & setup**
- `config/profile.yml` — target roles, salary, skills, scoring weights, dream/skip companies
- `cv.md` — your CV in plain Markdown, used for both evaluation and tailoring
- `portals.yml` — companies to track with ATS type and slug
- `.env` — `GEMINI_API_KEY` only; no other secrets needed

**Testing & CI**
- Full unit test suite: `test_tracker`, `test_scraper`, `test_gemini`, `test_config` (pytest + pytest-asyncio, all mocked — no real API calls)
- `pytest.ini` with `asyncio_mode = auto` and test path configuration
- GitHub Actions CI workflow: pytest matrix on Python 3.11 + 3.12, separate ruff lint/format job
- `pyproject.toml` `[project.optional-dependencies]`, `[tool.ruff]`, `[tool.pytest.ini_options]`

### Fixed
- Portal scanner: replaced sequential coroutine iteration with `asyncio.gather()` — scans run in parallel as originally intended
- `scan --eval`: now collects IDs of jobs inserted during the current scan and evaluates only those, not all jobs with `status="new"` in the database
- `pyproject.toml`: corrected stray opening parenthesis in rich version specifier (`rich(>=13.7.0` → `rich>=13.7.0`)

---

## Development history

| Commit | Type | Description |
|--------|------|-------------|
| `0970bd2d` | feat | Initial release — JobForge v1.0.0 (19 files) |
| `8720f172` | fix  | Concurrent portal scanning with asyncio.gather + Rich progress bar |
| `98ce7337` | feat | Gemini retry logic with exponential backoff (new gemini.py module) |
| `7ee98f14` | feat | Add search, open, and export commands |
| `818afaea` | fix  | scan --eval now targets only newly discovered jobs |
| `cca6dd16` | test | Full unit test suite (tracker, scraper, gemini, config) |
| `195398c1` | ci   | Add GitHub Actions workflow + pyproject.toml dev extras |
| `de0d132a` | fix  | Correct rich version specifier in pyproject.toml |
