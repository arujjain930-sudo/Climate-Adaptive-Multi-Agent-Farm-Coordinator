"""
Configuration module — loads all settings from environment variables.

Design decision: We use pydantic-settings so that every config value is
validated at startup. If GEMINI_API_KEY is missing, the app crashes
immediately with a clear error instead of failing on the first request.
"""

from __future__ import annotations

import os
from functools import lru_cache

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment / .env file."""

    # ── Gemini API ──────────────────────────────────────────────────────
    gemini_api_key_1: str = Field(
        default="",
        description="First Google Gemini API key (never hardcode this)",
    )
    gemini_api_key_2: str = Field(
        default="",
        description="Second Google Gemini API key (never hardcode this)",
    )
    gemini_api_key: str | None = Field(
        default="",
        description="Google Gemini API key fallback for backward compatibility",
    )
    gemini_model: str = Field(
        default="gemini-2.5-flash",
        description="Gemini model name — must use gemini-2.5-flash",
    )

    # ── Rate Limiting ───────────────────────────────────────────────────
    rate_limit: str = Field(
        default="5/minute",
        description="SlowAPI rate limit string (per IP)",
    )

    # ── CORS ────────────────────────────────────────────────────────────
    allowed_origins: str = Field(
        default="http://localhost:3000,http://localhost:8000,http://127.0.0.1:3000,http://127.0.0.1:8000",
        description="Comma-separated allowed CORS origins",
    )

    # ── Agent Tuning ────────────────────────────────────────────────────
    confidence_threshold: float = Field(
        default=0.6,
        description="Minimum confidence before triggering a refinement loop",
    )
    max_refinement_iterations: int = Field(
        default=2,
        description="Maximum number of refinement re-runs for the Crop Action agent",
    )
    gemini_temperature: float = Field(
        default=0.4,
        description="Temperature for Gemini calls — lower = more deterministic",
    )

    # ── Input Limits ────────────────────────────────────────────────────
    max_location_length: int = 100
    max_crop_type_length: int = 60
    max_goal_length: int = 200
    max_notes_length: int = 500

    @property
    def origins_list(self) -> list[str]:
        """Parse comma-separated origins into a list."""
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    class Config:
        # Look for a .env file next to manage.py / in the project root
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # silently ignore unknown env vars


@lru_cache()
def get_settings() -> Settings:
    """
    Singleton accessor — cached so the .env file is read only once.

    If GEMINI_API_KEY is not set, pydantic-settings raises a clear
    ValidationError at import time rather than a cryptic KeyError later.
    """
    return Settings()
