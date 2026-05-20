"""
JobForge — Gemini API wrapper with retry logic
Handles rate limits and transient errors gracefully via exponential backoff.
"""

import json
import re
import time
from typing import Any

import google.generativeai as genai
from rich.console import Console

from .config import get_gemini_key, get_gemini_model

console = Console()

# Gemini free tier: 15 requests/minute
_RATE_LIMIT_CODES = {429}   # HTTP 429 = Too Many Requests
_RETRY_EXCEPTIONS  = (Exception,)   # refined below per error message


def _init_model() -> genai.GenerativeModel:
    """Configure Gemini and return a model instance."""
    genai.configure(api_key=get_gemini_key())
    return genai.GenerativeModel(get_gemini_model())


def generate(
    prompt: str,
    *,
    max_retries: int = 4,
    initial_wait: float = 5.0,
    label: str = "Gemini",
) -> str:
    """
    Call Gemini with automatic retry and exponential backoff.

    Handles:
    - 429 rate-limit errors (backs off and retries)
    - Transient API failures (network blips, 500s)
    - Response blocked by safety filters (raises ValueError)

    Args:
        prompt:        The prompt string to send.
        max_retries:   How many times to retry before giving up.
        initial_wait:  Seconds to wait before the first retry (doubles each time).
        label:         Short label for log messages (e.g. "evaluator").

    Returns:
        The response text from Gemini.

    Raises:
        ValueError:   If the response is blocked or empty.
        RuntimeError: If all retries are exhausted.
    """
    model = _init_model()
    wait = initial_wait

    for attempt in range(1, max_retries + 2):   # +1 for the initial attempt
        try:
            response = model.generate_content(prompt)

            # Check for blocked response
            if not response.parts:
                finish = getattr(response, "prompt_feedback", None)
                raise ValueError(
                    f"Gemini blocked the response. Feedback: {finish}"
                )

            text = response.text.strip()
            if not text:
                raise ValueError("Gemini returned an empty response.")

            return text

        except Exception as exc:
            err = str(exc).lower()
            is_rate_limit = "429" in err or "quota" in err or "rate" in err
            is_transient  = "500" in err or "503" in err or "timeout" in err or "unavailable" in err

            if attempt > max_retries:
                raise RuntimeError(
                    f"{label}: all {max_retries} retries exhausted. Last error: {exc}"
                ) from exc

            if is_rate_limit or is_transient:
                console.print(
                    f"[yellow]⚠ {label}: {'rate limited' if is_rate_limit else 'transient error'} "
                    f"— retrying in {wait:.0f}s (attempt {attempt}/{max_retries})…[/yellow]"
                )
                time.sleep(wait)
                wait = min(wait * 2, 60.0)   # cap at 60s
            else:
                # Non-retryable error (bad API key, invalid model, etc.)
                raise


def parse_json_response(text: str) -> dict[str, Any]:
    """
    Parse a JSON response from Gemini, stripping markdown fences if present.

    Gemini sometimes wraps JSON in ```json ... ``` — this handles that.
    """
    text = text.strip()
    # Strip ```json ... ``` or ``` ... ``` fences
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
        text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        # Try to find a JSON object inside the text as a last resort
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        raise ValueError(
            f"Could not parse JSON from Gemini response. "
            f"First 200 chars: {text[:200]!r}"
        ) from exc
