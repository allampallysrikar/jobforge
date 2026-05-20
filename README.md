# JobForge

**AI-powered job search automation — built by Srikar Allampally**

[![CI](https://github.com/allampallysrikar/jobforge/actions/workflows/ci.yml/badge.svg)](https://github.com/allampallysrikar/jobforge/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![Gemini](https://img.shields.io/badge/Gemini_AI-Free_Tier-4285F4?style=flat&logo=google&logoColor=white)](https://aistudio.google.com)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Author](https://img.shields.io/badge/Built_by-Srikar_Allampally-000?style=flat)](https://github.com/allampallysrikar)

JobForge automates the most tedious parts of job hunting: finding roles, evaluating fit, generating tailored CVs, and tracking applications — all powered by Google Gemini's free API.

## Features

| Feature | Description |
|---------|-------------|
| **AI Job Evaluation** | Scores any job A–F across 7 dimensions using Gemini |
| **Tailored CV Generator** | Rewrites your CV with job-specific keywords, renders to PDF |
| **Portal Scanner** | Scans 15+ company career pages (Greenhouse, Lever, Ashby) |
| **Application Tracker** | SQLite pipeline: new → applied → interview → offer |
| **Terminal Dashboard** | Rich CLI to browse, filter, and manage your pipeline |
| **100% Free** | Gemini free tier: 15 req/min, 1M tokens/day — no credit card |

## Quick Start

```bash
# 1. Clone
git clone https://github.com/allampallysrikar/jobforge.git
cd jobforge

# 2. Install
pip install -e .
playwright install chromium

# 3. Get a FREE Gemini API key (no credit card)
#    → https://aistudio.google.com/apikey

# 4. Configure
cp .env.example .env
# Edit .env → add your GEMINI_API_KEY

cp config/profile.example.yml config/profile.yml
# Edit config/profile.yml → add your details, skills, salary expectations

# Create cv.md with your CV in markdown format

# 5. Check setup
jobforge doctor

# 6. Evaluate a job
jobforge eval https://jobs.ashbyhq.com/anthropic/senior-engineer
```

## Commands

```
# Evaluate
jobforge eval <url>                  Score a job A–F against your CV and profile
jobforge eval --text                 Evaluate by pasting a job description
jobforge eval <url> --pdf            Evaluate + generate tailored CV PDF

# CV generation
jobforge cv <job_id>                 Generate tailored CV PDF for a tracked job

# Scanning
jobforge scan                        Scan configured job portals for new listings
jobforge scan --eval                 Scan + auto-evaluate newly found jobs
jobforge scan --eval --max-eval 20   Cap auto-evaluation at 20 jobs per run

# Pipeline management
jobforge pipeline                    View full application pipeline
jobforge pipeline --grade B          Filter by minimum grade (A/B/C/D/F)
jobforge pipeline --status applied   Filter by status
jobforge view <job_id>               View detailed evaluation report
jobforge status <id> applied         Update application status
jobforge note <id> "text"            Add a note to a job

# Search & export
jobforge search <query>              Search jobs by title, company, or location
jobforge open <job_id>               Open job URL in browser
jobforge export                      Export pipeline to CSV (default)
jobforge export --format json        Export as JSON
jobforge export --grade B            Export only grade B+ jobs
jobforge export --status applied     Export by status

# Info
jobforge stats                       Pipeline statistics
jobforge doctor                      Check all dependencies and setup
```

## How It Works

```
You run:  jobforge eval https://company.com/jobs/role
                ↓
  1. Playwright fetches the job page (handles JS)
  2. Gemini reads your CV + profile + job description
  3. Scores the role on 7 weighted dimensions (A–F)
  4. Saves evaluation report to reports/
  5. Adds job to your SQLite tracker
  6. (Optional) Generates tailored PDF CV with job-specific keywords
```

## Configuration

### Your Profile (`config/profile.yml`)
Fill in your target roles, salary expectations, skills, and scoring weights. The more detail you provide, the more accurate the evaluations.

### Your CV (`cv.md`)
Write your CV in markdown format. Gemini uses this to evaluate fit and generate tailored versions.

### Job Portals (`portals.yml`)
Copy `portals.example.yml` → `portals.yml` and add the companies you want to track. Supports Greenhouse, Lever, and Ashby ATS platforms.

## Setup Requirements

- Python 3.11+
- Gemini API key (free at [aistudio.google.com](https://aistudio.google.com/apikey))
- Chromium (installed via `playwright install chromium`)

See [docs/SETUP.md](docs/SETUP.md) for detailed setup instructions.

## Project Structure

```
jobforge/
├── jobforge/
│   ├── main.py          CLI entry point (Typer commands)
│   ├── config.py        Profile, CV, and portal loading
│   ├── scraper.py       Concurrent Greenhouse/Lever/Ashby scanner
│   ├── evaluator.py     Gemini-powered job scoring (A–F)
│   ├── cv_generator.py  Tailored CV generation
│   ├── gemini.py        Shared Gemini API wrapper (retry + backoff)
│   ├── tracker.py       SQLite job database
│   ├── dashboard.py     Rich terminal UI
│   └── pdf_gen.py       Playwright HTML→PDF renderer
├── templates/
│   └── cv.html          Jinja2 CV template
├── config/
│   └── profile.example.yml
├── tests/               Full unit test suite (no API calls)
├── docs/SETUP.md        Detailed setup guide
├── portals.example.yml  Sample job portal config
├── .env.example
└── pyproject.toml
```

## License

MIT License — Copyright (c) 2026 Srikar Allampally

See [LICENSE](LICENSE) for details.

## Connect

[![GitHub](https://img.shields.io/badge/github.com/allampallysrikar-000?style=flat&logo=github)](https://github.com/allampallysrikar)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-0A66C2?style=flat&logo=linkedin&logoColor=white)](https://linkedin.com/in/allampallysrikar)
