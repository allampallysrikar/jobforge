# JobForge — Setup Guide

## 1. Prerequisites

- **Python 3.11+** — [python.org/downloads](https://python.org/downloads)
- **pip** — comes with Python
- **Git** — [git-scm.com](https://git-scm.com)

## 2. Install JobForge

```bash
git clone https://github.com/allampallysrikar/jobforge.git
cd jobforge
pip install -e .
playwright install chromium
```

## 3. Get a Free Gemini API Key

1. Go to [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
2. Sign in with your Google account
3. Click **"Create API Key"**
4. Copy the key

**Free tier limits:** 15 requests/minute, 1 million tokens/day — more than enough for daily job hunting.

## 4. Configure Your Environment

```bash
cp .env.example .env
```

Edit `.env`:
```env
GEMINI_API_KEY=your_key_here
```

## 5. Set Up Your Profile

```bash
cp config/profile.example.yml config/profile.yml
```

Edit `config/profile.yml` — fill in:
- Your name, email, location
- Target job titles and domains
- Salary expectations
- Your skills (be specific — these drive keyword matching)
- What you value in a company
- Scoring weights (how much each dimension matters to you)

## 6. Add Your CV

Create `cv.md` in the project root with your CV in markdown:

```markdown
# Your Name

Senior Software Engineer with 5 years building scalable backend systems...

## Experience

### Senior Engineer — Company Name (2022–Present)
- Built X that achieved Y
- Led team of N engineers to deliver Z

### Engineer — Previous Company (2020–2022)
- ...

## Skills
Python, TypeScript, AWS, PostgreSQL, Docker...

## Education
BSc Computer Science — University Name, 2020
```

The more detail you include, the better the AI evaluations and CV tailoring.

## 7. Configure Job Portals (Optional)

```bash
cp portals.example.yml portals.yml
```

Edit `portals.yml` — add the companies you want to scan. Each company needs:
- `name`: Display name
- `ats`: The ATS platform (`greenhouse`, `lever`, or `ashby`)
- `slug`: The company's slug on that platform

To find a company's slug:
- **Greenhouse**: Look at `boards.greenhouse.io/<slug>`
- **Lever**: Look at `jobs.lever.co/<slug>`
- **Ashby**: Look at `jobs.ashbyhq.com/<slug>`

## 8. Verify Setup

```bash
jobforge doctor
```

This checks Python version, API key, profile, CV, and Playwright.

## 9. First Evaluation

```bash
jobforge eval https://jobs.ashbyhq.com/anthropic/senior-engineer
```

Or paste a job description:
```bash
jobforge eval --text
# paste the job description, then Ctrl+D
```

## Folder Structure After Setup

```
jobforge/
├── .env                    ← your API key (gitignored)
├── cv.md                   ← your CV (gitignored)
├── portals.yml             ← your portal config (gitignored)
├── config/
│   └── profile.yml         ← your profile (gitignored)
├── data/
│   └── jobforge.db         ← your job tracker (gitignored)
├── output/                 ← generated PDF CVs (gitignored)
└── reports/                ← evaluation reports (gitignored)
```

Everything in `data/`, `output/`, and `reports/` is gitignored — your personal data never gets committed.
