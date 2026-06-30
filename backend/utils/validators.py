"""
Input validation and sanitisation helpers.

Design rationale:
  • Every user-supplied string is stripped, length-checked, and scrubbed of
    potentially dangerous characters *before* it reaches any agent or prompt.
  • We reject outright if the value is empty after cleaning — this avoids
    sending blank prompts to Gemini, which would waste quota.
"""

from __future__ import annotations

import re
from typing import Optional

from backend.config import get_settings

# Characters we explicitly allow in free-text fields.
# Everything else is stripped to prevent prompt-injection and XSS.
_SAFE_TEXT_RE = re.compile(r"[^a-zA-Z0-9\s,.\-'\"()/:;!?&#+@°%]")

# Location names may contain accented letters and a few punctuation marks.
_SAFE_LOCATION_RE = re.compile(r"[^a-zA-ZÀ-ÿ0-9\s,.\-'()]")

# Crop type — simple alpha + spaces + hyphens
_SAFE_CROP_RE = re.compile(r"[^a-zA-ZÀ-ÿ0-9\s\-'()]")


def _strip_dangerous(value: str, pattern: re.Pattern) -> str:
    """Remove characters not matching the allowed pattern."""
    return pattern.sub("", value).strip()


def validate_location(location: str | None) -> str:
    """
    Validate and sanitise a location string.

    Returns the cleaned string or raises ValueError.
    """
    settings = get_settings()

    if not location or not location.strip():
        raise ValueError("Location is required and cannot be empty.")

    cleaned = _strip_dangerous(location.strip(), _SAFE_LOCATION_RE)

    if not cleaned:
        raise ValueError("Location contains only invalid characters.")

    if len(cleaned) > settings.max_location_length:
        raise ValueError(
            f"Location must be at most {settings.max_location_length} characters."
        )

    return cleaned


def validate_crop_type(crop_type: str | None) -> str:
    """
    Validate and sanitise a crop type string.

    Returns the cleaned string or raises ValueError.
    """
    settings = get_settings()

    if not crop_type or not crop_type.strip():
        raise ValueError("Crop type is required and cannot be empty.")

    cleaned = _strip_dangerous(crop_type.strip(), _SAFE_CROP_RE)

    if not cleaned:
        raise ValueError("Crop type contains only invalid characters.")

    if len(cleaned) > settings.max_crop_type_length:
        raise ValueError(
            f"Crop type must be at most {settings.max_crop_type_length} characters."
        )

    return cleaned


def validate_optional_text(
    value: str | None,
    field_name: str,
    max_length: int,
) -> Optional[str]:
    """
    Validate an optional free-text field (goal, notes).

    Returns None if the value is empty/None, or the cleaned string.
    Raises ValueError if the value exceeds the length limit after cleaning.
    """
    if not value or not value.strip():
        return None

    cleaned = _strip_dangerous(value.strip(), _SAFE_TEXT_RE)

    if len(cleaned) > max_length:
        raise ValueError(
            f"{field_name} must be at most {max_length} characters."
        )

    return cleaned if cleaned else None


def validate_analyze_input(data: dict) -> dict:
    """
    Validate the full /api/analyze request body.

    Returns a dict of cleaned values ready for the orchestrator.
    Raises ValueError with a human-readable message on failure.
    """
    settings = get_settings()

    location = validate_location(data.get("location"))
    crop_type = validate_crop_type(data.get("crop_type"))
    farming_goal = validate_optional_text(
        data.get("farming_goal"), "Farming goal", settings.max_goal_length
    )
    notes = validate_optional_text(
        data.get("notes"), "Notes", settings.max_notes_length
    )

    return {
        "location": location,
        "crop_type": crop_type,
        "farming_goal": farming_goal or "maximize yield",
        "notes": notes or "",
    }
