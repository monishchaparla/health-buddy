"""Gemini structured output with a model fallback chain (pattern from CarbonTrace's extract.py).

404 (retired model) and 429 (quota) move on to the next model; 5xx and timeouts do too. If every
model is rate limited we raise RateLimited so callers can fall back to rules and tell the user.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

DEFAULT_MODELS = "gemini-3.6-flash,gemini-3.5-flash,gemini-3.1-flash-lite"


class AIUnavailable(RuntimeError):
    pass


class RateLimited(AIUnavailable):
    pass


def models() -> list[str]:
    return [m.strip() for m in os.environ.get("GEMINI_MODELS", DEFAULT_MODELS).split(",") if m.strip()]


def enabled() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY"))


def generate(contents: list, schema: type[BaseModel]) -> tuple[BaseModel, str]:
    """Returns (parsed, model). Raises AIUnavailable / RateLimited."""
    if not enabled():
        raise AIUnavailable("GEMINI_API_KEY is not set")
    from google import genai
    from google.genai import errors, types

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    attempts = []
    for model in models():
        try:
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=schema,
                    temperature=0,
                    thinking_config=types.ThinkingConfig(thinking_level="low"),
                    http_options=types.HttpOptions(timeout=60_000),
                ),
            )
        except errors.ClientError as exc:
            attempts.append(exc.code)
            if exc.code not in (404, 429):
                raise AIUnavailable(f"Gemini rejected the request ({exc.code})") from exc
            continue
        except Exception as exc:  # 5xx, timeouts, connection drops
            attempts.append(type(exc).__name__)
            time.sleep(1)
            continue
        parsed = response.parsed if isinstance(response.parsed, schema) else schema.model_validate_json(response.text)
        return parsed, model
    if attempts and all(a == 429 for a in attempts):
        raise RateLimited("All Gemini models are rate limited right now")
    raise AIUnavailable(f"All Gemini models failed: {attempts}")
