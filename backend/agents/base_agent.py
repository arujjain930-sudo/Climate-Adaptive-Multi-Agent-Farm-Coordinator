"""
Base agent class — shared Gemini API call logic.

Architecture notes:
  • All three specialist agents inherit from BaseAgent so the Gemini
    configuration, retry logic, and JSON extraction live in one place.
  • The google-generativeai SDK is synchronous, so we wrap calls in
    asyncio.to_thread() to avoid blocking the event loop.
  • JSON extraction is defensive: we try json.loads first, then fall back
    to regex-based extraction if Gemini wraps the JSON in markdown fences.
"""

from __future__ import annotations

import asyncio
import json
import logging
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
        # Use gemini_api_key_1 if available as string, otherwise fall back to gemini_api_key
        key1 = getattr(settings, "gemini_api_key_1", None)
        api_key = key1 if isinstance(key1, str) else getattr(settings, "gemini_api_key", None)
        
        # If no string fallback is available, handle gracefully
        if not isinstance(api_key, str) and api_key is not None:
            # Let mock objects pass through
            pass
        elif not api_key:
            api_key = "mock-key"

        genai.configure(api_key=api_key)

        self._model = genai.GenerativeModel(
            model_name=settings.gemini_model,
            generation_config=genai.types.GenerationConfig(
                temperature=settings.gemini_temperature,
                max_output_tokens=2048,
            ),
        )
        logger.info("[%s] Initialised with model %s", self.agent_name, settings.gemini_model)

    # ── Core Gemini call ─────────────────────────────────────────────

    async def call_gemini(self, prompt: str) -> str:
        """
        Send *prompt* to Gemini and return the raw text response.

        Runs the synchronous SDK call in a thread so we don't block
        the asyncio event loop (important because Weather + Soil
        agents run in parallel via asyncio.gather).

        Includes retry logic with exponential backoff if a call fails with a 429 error.
        Retries up to 4 times, waiting 4, 15, 30, then 30 seconds.
        The free tier allows only 5 RPM, so longer backoff gives the quota time to reset.
        """
        # Load settings and compile keys list
        settings = get_settings()
        api_keys = []
        key1 = getattr(settings, "gemini_api_key_1", None)
        key2 = getattr(settings, "gemini_api_key_2", None)
        
        if isinstance(key1, str):
            api_keys.append(key1)
        if isinstance(key2, str):
            api_keys.append(key2)
            
        if not api_keys:
            key_fallback = getattr(settings, "gemini_api_key", None)
            if isinstance(key_fallback, str):
                api_keys.append(key_fallback)

        retries = 4
        backoff_delays = [4, 15, 30, 30]
        for attempt in range(retries + 1):
            # Select key and configure under lock to avoid race conditions
            if api_keys:
                async with _key_rotation_lock:
                    global _key_rotation_index
                    key = api_keys[_key_rotation_index % len(api_keys)]
                    logger.info(
                        "[%s] Rotating to Gemini API key index %d (ending in ...%s) for attempt %d/%d",
                        self.agent_name,
                        _key_rotation_index % len(api_keys),
                        key[-4:] if len(key) >= 4 else key,
                        attempt + 1,
                        retries + 1,
                    )
                    _key_rotation_index += 1
                    
                    genai.configure(api_key=key)
                    
                    # Clear and resolve client synchronously under lock
                    self._model._client = None
                    self._model._async_client = None
                    
                    from google.generativeai import client as genai_client
                    self._model._client = genai_client.get_default_generative_client()

            logger.info(
                "[%s] Sending prompt (%d chars) - Attempt %d/%d",
                self.agent_name,
                len(prompt),
                attempt + 1,
                retries + 1,
            )
            try:
                response = await asyncio.to_thread(
                    self._model.generate_content, prompt
                )
                text = response.text.strip()
                logger.info("[%s] Received response (%d chars)", self.agent_name, len(text))
                return text
            except Exception as exc:
                # Check if it is a 429 (ResourceExhausted / Rate Limit Exceeded) error
                is_429 = False
                try:
                    from google.api_core import exceptions as google_exceptions
                    if isinstance(exc, google_exceptions.ResourceExhausted):
                        is_429 = True
                except ImportError:
                    pass

                if hasattr(exc, "status_code") and exc.status_code == 429:
                    is_429 = True
                elif hasattr(exc, "code") and exc.code == 429:
                    is_429 = True

                exc_str = str(exc)
                if "429" in exc_str or "ResourceExhausted" in exc_str or "rate limit" in exc_str.lower() or "quota" in exc_str.lower():
                    is_429 = True

                # If it's a 429 and we have retries left, wait and retry
                if is_429 and attempt < retries:
                    delay = backoff_delays[attempt]
                    logger.warning(
                        "[%s] Gemini call failed with 429/Rate Limit. Retrying in %ds (Attempt %d/%d). Error: %s",
                        self.agent_name,
                        delay,
                        attempt + 1,
                        retries,
                        exc,
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error("[%s] Gemini call failed: %s", self.agent_name, exc)
                    raise

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
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        # Attempt 2: extract from markdown code fences
        match = _JSON_BLOCK_RE.search(raw)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # Attempt 3: find first { ... } block
        try:
            start = raw.index("{")
            end = raw.rindex("}") + 1
            return json.loads(raw[start:end])
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
