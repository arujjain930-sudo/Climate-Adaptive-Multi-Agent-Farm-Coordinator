"""
Base agent class — shared Gemini API call logic.

Architecture notes:
  • All three specialist agents inherit from BaseAgent so the Gemini
    configuration, retry logic, and JSON extraction live in one place.
  • The google-generativeai SDK is synchronous, so we wrap calls in
    asyncio.to_thread() to avoid blocking the event loop.
  • JSON extraction is defensive: we try json.loads first, then fall back
    to regex-based extraction if Gemini wraps the JSON in markdown fences.
  • Key rotation creates a fresh GenerativeModel per call to avoid
    manipulating private SDK internals (safe across all SDK versions).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from typing import Any

import google.generativeai as genai

from backend.config import get_settings

logger = logging.getLogger("farm_coordinator.base_agent")

# Pre-compile regex to extract JSON from markdown code fences or raw text
_JSON_BLOCK_RE = re.compile(
    r"```(?:json)?\s*\n?(.*?)\n?\s*```",
    re.DOTALL,
)

# Global variables for thread-safe API key rotation across agents
_key_rotation_lock = asyncio.Lock()
_key_rotation_index = 0


def _get_api_keys() -> list[str]:
    """
    Collect valid (non-empty) API keys from settings.
    Returns a list of usable key strings.
    """
    settings = get_settings()
    keys: list[str] = []
    for attr in ("gemini_api_key_1", "gemini_api_key_2", "gemini_api_key"):
        val = getattr(settings, attr, None)
        if isinstance(val, str) and len(val) > 4:
            keys.append(val)
    return keys


class BaseAgent:
    """
    Abstract base for all farm-coordinator agents.

    Subclasses must implement ``async def run(**kwargs) -> dict``.
    """

    # Subclasses override these for logging clarity
    agent_name: str = "BaseAgent"

    def __init__(self) -> None:
        settings = get_settings()
        # Configure the SDK once per agent instance.
        keys = _get_api_keys()
        api_key = keys[0] if keys else "placeholder-key"
        genai.configure(api_key=api_key)

        self._settings = settings
        logger.info("[%s] Initialised with model %s", self.agent_name, settings.gemini_model)

    # ── Core Gemini call ─────────────────────────────────────────────

    async def call_gemini(self, prompt: str) -> str:
        """
        Send *prompt* to Gemini and return the raw text response.

        Runs the synchronous SDK call in a thread so we don't block
        the asyncio event loop (important because Weather + Soil
        agents run in parallel via asyncio.gather).

        Key rotation creates a fresh GenerativeModel per call so we
        never touch private SDK internals like _client — this is safe
        across all versions of google-generativeai.

        On serverless platforms (Vercel), retries use shorter delays
        to stay within the function execution timeout.
        """
        api_keys = _get_api_keys()
        settings = self._settings

        # Detect serverless environment and shorten delays
        is_serverless = bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
        retries = 2 if is_serverless else 4
        backoff_delays = [2, 4, 8] if is_serverless else [4, 15, 30, 30]

        for attempt in range(retries + 1):
            try:
                # Select key and build a fresh model under lock
                if api_keys:
                    async with _key_rotation_lock:
                        global _key_rotation_index
                        key = api_keys[_key_rotation_index % len(api_keys)]
                        logger.info(
                            "[%s] Using API key index %d (ending in ...%s) — attempt %d/%d",
                            self.agent_name,
                            _key_rotation_index % len(api_keys),
                            key[-4:] if len(key) >= 4 else "****",
                            attempt + 1,
                            retries + 1,
                        )
                        _key_rotation_index += 1
                else:
                    key = "placeholder-key"

                # Configure SDK with selected key and create a fresh model
                # This avoids touching private SDK internals
                genai.configure(api_key=key)
                model = genai.GenerativeModel(
                    model_name=settings.gemini_model,
                    generation_config=genai.types.GenerationConfig(
                        temperature=settings.gemini_temperature,
                        max_output_tokens=2048,
                    ),
                )

                logger.info(
                    "[%s] Sending prompt (%d chars) — attempt %d/%d",
                    self.agent_name,
                    len(prompt),
                    attempt + 1,
                    retries + 1,
                )

                response = await asyncio.to_thread(model.generate_content, prompt)
                text = response.text.strip()
                logger.info("[%s] Received response (%d chars)", self.agent_name, len(text))
                return text

            except Exception as exc:
                exc_str = str(exc)

                # Detect rate-limit / quota errors
                is_429 = any(kw in exc_str.lower() for kw in [
                    "429", "resourceexhausted", "rate limit", "quota",
                    "resource_exhausted", "too many requests",
                ])

                if is_429 and attempt < retries:
                    delay = backoff_delays[min(attempt, len(backoff_delays) - 1)]
                    logger.warning(
                        "[%s] Rate-limited (429). Retrying in %ds (attempt %d/%d): %s",
                        self.agent_name, delay, attempt + 1, retries, exc,
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error("[%s] Gemini call failed: %s", self.agent_name, exc)
                    raise

        # Should never reach here, but just in case
        raise RuntimeError(f"[{self.agent_name}] All {retries + 1} Gemini attempts exhausted")

    # ── JSON parsing helpers ─────────────────────────────────────────

    def parse_json_response(self, raw: str, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        Extract a JSON object from Gemini's response.

        Gemini sometimes wraps JSON in ```json ... ``` fences, or adds
        commentary before/after. We handle both cases.

        If parsing fails entirely we return *fallback* (or a minimal
        error dict) so the pipeline never crashes on bad model output.
        """
        # Attempt 1: direct parse
        # Attempt 1: direct parse
        try:
            val = json.loads(raw)
            if isinstance(val, dict):
                return val
        except json.JSONDecodeError:
            pass

        # Attempt 2: extract from markdown code fences
        match = _JSON_BLOCK_RE.search(raw)
        if match:
            try:
                val = json.loads(match.group(1))
                if isinstance(val, dict):
                    return val
            except json.JSONDecodeError:
                pass

        # Attempt 3: find first { ... } block
        try:
            start = raw.index("{")
            end = raw.rindex("}") + 1
            val = json.loads(raw[start:end])
            if isinstance(val, dict):
                return val
        except (ValueError, json.JSONDecodeError):
            pass

        logger.warning(
            "[%s] Could not parse JSON from response (first 200 chars): %s",
            self.agent_name,
            raw[:200],
        )
        return fallback or {"error": "Failed to parse agent response", "raw_snippet": raw[:300]}

    # ── Abstract run method ──────────────────────────────────────────

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        """Subclasses implement this to execute their specific task."""
        raise NotImplementedError("Subclasses must implement run()")
