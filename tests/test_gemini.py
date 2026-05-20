"""
Tests for jobforge.gemini — JSON parsing and retry logic.
Uses mocks only — no real API calls.
"""

import json
import pytest
from unittest.mock import MagicMock, patch


# ── parse_json_response ───────────────────────────────────────────────────────

def test_parse_clean_json():
    from jobforge.gemini import parse_json_response
    data = parse_json_response('{"grade": "A", "score": 4.5}')
    assert data["grade"] == "A"
    assert data["score"] == 4.5


def test_parse_json_with_backtick_fence():
    from jobforge.gemini import parse_json_response
    text = '```json\n{"grade": "B"}\n```'
    data = parse_json_response(text)
    assert data["grade"] == "B"


def test_parse_json_with_plain_fence():
    from jobforge.gemini import parse_json_response
    text = '```\n{"grade": "C"}\n```'
    data = parse_json_response(text)
    assert data["grade"] == "C"


def test_parse_json_embedded_in_text():
    """JSON buried inside text should be extracted."""
    from jobforge.gemini import parse_json_response
    text = 'Here is the analysis:\n{"grade": "D", "score": 2.0}\nEnd.'
    data = parse_json_response(text)
    assert data["grade"] == "D"


def test_parse_json_invalid_raises():
    from jobforge.gemini import parse_json_response
    with pytest.raises(ValueError, match="Could not parse JSON"):
        parse_json_response("This is definitely not JSON at all.")


# ── generate with retry ───────────────────────────────────────────────────────

def _make_mock_model(responses):
    """Build a mock GenerativeModel that cycles through a list of responses."""
    model = MagicMock()
    model.generate_content.side_effect = responses
    return model


def _mock_response(text: str):
    r = MagicMock()
    r.parts = [MagicMock()]  # non-empty → not blocked
    r.text = text
    return r


@patch("jobforge.gemini._init_model")
def test_generate_success_first_try(mock_init):
    from jobforge.gemini import generate
    mock_init.return_value = _make_mock_model([_mock_response("Hello!")])

    result = generate("Say hello")
    assert result == "Hello!"


@patch("jobforge.gemini.time.sleep")   # don't actually sleep in tests
@patch("jobforge.gemini._init_model")
def test_generate_retries_on_rate_limit(mock_init, mock_sleep):
    from jobforge.gemini import generate

    rate_limit_exc = Exception("HTTP 429: Too Many Requests")
    ok_response    = _mock_response("OK!")

    mock_init.return_value = _make_mock_model([rate_limit_exc, ok_response])

    result = generate("prompt", initial_wait=0.01)
    assert result == "OK!"
    assert mock_sleep.called   # backoff was triggered


@patch("jobforge.gemini.time.sleep")
@patch("jobforge.gemini._init_model")
def test_generate_raises_after_max_retries(mock_init, mock_sleep):
    from jobforge.gemini import generate

    always_fail = Exception("429 rate limit")
    mock_init.return_value = _make_mock_model([always_fail] * 10)

    with pytest.raises(RuntimeError, match="retries exhausted"):
        generate("prompt", max_retries=2, initial_wait=0.01)


@patch("jobforge.gemini._init_model")
def test_generate_raises_immediately_on_bad_key(mock_init):
    """A 401/invalid-key error should NOT be retried."""
    from jobforge.gemini import generate

    bad_key_exc = Exception("API key not valid. Please pass a valid API key.")
    mock_init.return_value = _make_mock_model([bad_key_exc])

    with pytest.raises(Exception, match="API key not valid"):
        generate("prompt", max_retries=3)


@patch("jobforge.gemini._init_model")
def test_generate_raises_on_blocked_response(mock_init):
    from jobforge.gemini import generate

    blocked = MagicMock()
    blocked.parts = []   # empty parts → blocked
    mock_init.return_value = _make_mock_model([blocked])

    with pytest.raises(ValueError, match="blocked"):
        generate("prompt", max_retries=0)
