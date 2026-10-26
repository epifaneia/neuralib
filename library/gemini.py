"""Calls to Google's Gemini API over REST.

The key travels in a header, never in the URL. A rate-limit answer is not retried:
the caller hears about it and the page says so, so a busy day cannot turn into a bill.
"""
import json
import urllib.error
import urllib.request

from django.conf import settings

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:{method}"


class GeminiError(Exception):
    """Gemini could not answer (no key, network, bad response)."""


class QuotaExceeded(GeminiError):
    """The provider's free quota is used up for now."""


def call(model, method, payload, key=None):
    key = key or settings.GEMINI_API_KEY
    if not key:
        raise GeminiError("No Gemini API key is set.")
    request = urllib.request.Request(
        API.format(model=model, method=method),
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        if error.code == 429:
            raise QuotaExceeded("The Gemini quota is used up for now.") from error
        raise GeminiError(f"Gemini answered HTTP {error.code}.") from error
    except OSError as error:
        raise GeminiError("Gemini could not be reached.") from error


def generated_text(answer):
    """The text of the first candidate of a generateContent answer."""
    try:
        return answer["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError) as error:
        raise GeminiError("Gemini returned no text.") from error
