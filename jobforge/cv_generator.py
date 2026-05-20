"""
JobForge — CV Generator
Tailors your CV for a specific job using Gemini, then renders to HTML
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import google.generativeai as genai
from jinja2 import Environment, FileSystemLoader
from rich.console import Console

from .config import (
    get_gemini_key, get_gemini_model, load_profile, load_cv,
    profile_to_text, TEMPLATES_DIR
)
from .evaluator import Evaluation

console = Console()

CV_PROMPT = """You are an expert CV writer and ATS optimization specialist.

Your task: Tailor the candidate's CV for this specific job posting.

Rules:
1. Keep ALL facts truthful — never invent experience or skills
2. Reorder and rephrase bullet points to match the job's language
3. Add relevant keywords from the job description naturally
4. Adjust the summary/headline to match the role
5. Keep the same work history — just optimize the presentation
6. ATS-optimize: use exact keywords from the job description
7. Keep it to 1-2 pages worth of content

═══════════════════════════════════════
CANDIDATE PROFILE:
{profile}

═══════════════════════════════════════
ORIGINAL CV:
{cv}

═══════════════════════════════════════
JOB TITLE: {job_title}
COMPANY: {company}
KEY KEYWORDS: {keywords}
TAILORING TIPS: {tailoring_tips}

JOB DESCRIPTION:
{job_description}

═══════════════════════════════════════

Return ONLY valid JSON, no markdown fences:

{{
  "headline": "Senior Software Engineer | AI/ML Infrastructure",
  "summary": "2-3 sentence professional summary tailored to this specific role",
  "experience": [
    {{
      "title": "Job Title",
      "company": "Company Name",
      "period": "Jan 2022 – Present",
      "location": "City, Country / Remote",
      "bullets": [
        "Achievement-focused bullet with metrics and keywords",
        "Another strong bullet point"
      ]
    }}
  ],
  "skills": {{
    "primary": ["Most relevant skills for THIS job"],
    "secondary": ["Supporting skills"],
    "tools": ["Tools and platforms"]
  }},
  "education": [
    {{
      "degree": "BSc Computer Science",
      "institution": "University Name",
      "year": "2019",
      "notes": "Relevant coursework or achievements"
    }}
  ],
  "certifications": [],
  "projects": [
    {{
      "name": "Project Name",
      "description": "One-line description",
      "tech": ["Python", "AWS"],
      "url": "https://github.com/..."
    }}
  ],
  "keywords_added": ["list of keywords you injected"]
}}"""


@dataclass
class TailoredCV:
    headline: str
    summary: str
    experience: list[dict]
    skills: dict[str, list[str]]
    education: list[dict]
    certifications: list[dict]
    projects: list[dict]
    keywords_added: list[str]
    job_title: str
    company: str
    raw: dict[str, Any]


def generate_tailored_cv(
    job_description: str,
    evaluation: Evaluation | None = None,
    job_title: str = "",
    company: str = "",
) -> TailoredCV:
    """
    Generate a tailored CV for a specific job.
    Optionally uses evaluation data for better tailoring.
    """
    profile = load_profile()
    cv = load_cv()

    model_name = get_gemini_model()
    genai.configure(api_key=get_gemini_key())
    model = genai.GenerativeModel(model_name)

    # Use evaluation data if available
    keywords = []
    tailoring_tips = []
    if evaluation:
        keywords = evaluation.keywords
        tailoring_tips = evaluation.tailoring_tips
        job_title = job_title or evaluation.title
        company = company or evaluation.company

    prompt = CV_PROMPT.format(
        profile=profile_to_text(profile),
        cv=cv,
        job_title=job_title,
        company=company,
        keywords=", ".join(keywords[:20]) if keywords else "extract from JD",
        tailoring_tips="\n".join(f"- {t}" for t in tailoring_tips) if tailoring_tips else "optimize for job",
        job_description=job_description,
    )

    console.print("[dim]✏ Generating tailored CV with Gemini...[/dim]")
    response = model.generate_content(prompt)

    text = response.text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    raw = json.loads(text)

    return TailoredCV(
        headline=raw.get("headline", ""),
        summary=raw.get("summary", ""),
        experience=raw.get("experience", []),
        skills=raw.get("skills", {}),
        education=raw.get("education", []),
        certifications=raw.get("certifications", []),
        projects=raw.get("projects", []),
        keywords_added=raw.get("keywords_added", []),
        job_title=job_title,
        company=company,
        raw=raw,
    )


def render_cv_html(cv_data: TailoredCV, profile: dict | None = None) -> str:
    """Render the tailored CV data into HTML using the template."""
    if profile is None:
        profile = load_profile()

    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    template = env.get_template("cv.html")

    personal = profile.get("personal", {})

    return template.render(
        name=personal.get("name", "Your Name"),
        email=personal.get("email", ""),
        phone=personal.get("phone", ""),
        location=personal.get("location", ""),
        linkedin=personal.get("linkedin", ""),
        github=personal.get("github", ""),
        website=personal.get("website", ""),
        headline=cv_data.headline,
        summary=cv_data.summary,
        experience=cv_data.experience,
        skills=cv_data.skills,
        education=cv_data.education,
        certifications=cv_data.certifications,
        projects=cv_data.projects,
    )
