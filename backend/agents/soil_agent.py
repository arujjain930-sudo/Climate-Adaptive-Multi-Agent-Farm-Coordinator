"""
Soil Parameter Agent — looks up soil profiles and interprets them with Gemini.

Responsibility:
  1. Look up the rule-based soil profile for the location + crop.
  2. Send the profile data to Gemini for agronomic interpretation.
  3. Return a structured soil health summary.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from backend.agents.base_agent import BaseAgent
from backend.prompts.templates import SOIL_ANALYSIS_PROMPT
from backend.tools.soil_profiles import get_soil_profile

logger = logging.getLogger("farm_coordinator.soil_agent")


class SoilParameterAgent(BaseAgent):
    """Looks up soil data → interprets suitability for a specific crop."""

    agent_name = "SoilParameterAgent"

    async def run(
        self,
        *,
        location: str,
        crop_type: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Execute the soil analysis pipeline.

        Returns a dict with:
          - ``raw_soil``: the rule-based soil profile
          - ``analysis``: Gemini's structured interpretation
        """
        # ── Step 1: Look up soil profile ────────────────────────────
        logger.info("[%s] Looking up soil for '%s' / '%s'", self.agent_name, location, crop_type)
        raw_soil = get_soil_profile(location, crop_type)

        # ── Step 2: Build prompt and call Gemini ────────────────────
        prompt = SOIL_ANALYSIS_PROMPT.format(
            crop_type=crop_type,
            location=location,
            soil_data=json.dumps(raw_soil, indent=2, default=str),
            match_quality=raw_soil.get("match_quality", "unknown"),
        )

        try:
            raw_response = await self.call_gemini(prompt)
            local_fallback = get_dynamic_soil_fallback(raw_soil, crop_type)
            analysis = self.parse_json_response(raw_response, fallback=local_fallback)
        except Exception as exc:
            logger.error("[%s] Gemini interpretation failed: %s", self.agent_name, exc)
            analysis = get_dynamic_soil_fallback(raw_soil, crop_type)
            analysis["error"] = str(exc)

        # Ensure confidence key exists
        if "confidence" not in analysis:
            analysis["confidence"] = 0.5

        return {
            "raw_soil": raw_soil,
            "analysis": analysis,
        }


def get_dynamic_soil_fallback(raw_soil: dict[str, Any], crop_type: str) -> dict[str, Any]:
    soil_type = raw_soil.get("soil_type", "Loam")
    ph = raw_soil.get("ph_range", "6.5")
    drainage = raw_soil.get("drainage_quality", "good")
    fertility = raw_soil.get("fertility_rating", "medium")
    salinity = raw_soil.get("salinity_risk", "low")

    # Assess pH
    ph_val = 6.5
    try:
        if "–" in ph:
            ph_val = (float(ph.split("–")[0]) + float(ph.split("–")[1])) / 2
        elif "-" in ph:
            ph_val = (float(ph.split("-")[0]) + float(ph.split("-")[1])) / 2
        else:
            ph_val = float(ph)
    except Exception:
        pass

    issues = []
    amendments = []
    strengths = [f"Soil texture is {soil_type}"]

    if ph_val < 5.5:
        issues.append("Soil is strongly acidic, limiting phosphorus availability.")
        amendments.append("Apply agricultural lime (calcium carbonate) to increase soil pH.")
    elif ph_val > 7.8:
        issues.append("Soil is alkaline, limiting micronutrient uptake.")
        amendments.append("Apply elemental sulfur or organic compost to lower pH.")
    else:
        strengths.append(f"Optimal soil pH ({ph}) for nutrient availability.")

    if drainage.lower() == "poor":
        issues.append("Poor soil drainage may lead to root asphyxiation.")
        amendments.append("Plant on raised beds and avoid over-irrigation.")
    else:
        strengths.append(f"Soil drainage quality is {drainage}.")

    if fertility.lower() == "low":
        issues.append("Low overall nutrient reserves.")
        amendments.append("Incorporate organic manure and apply balanced NPK fertilizers.")
    else:
        strengths.append(f"Soil fertility rating is {fertility}.")

    return {
        "suitability_rating": "good" if ph_val >= 6.0 and ph_val <= 7.5 else "moderate",
        "ph_assessment": f"Soil pH is {ph}.",
        "nutrient_assessment": f"Fertility is {fertility}. Nitrogen: {raw_soil.get('nitrogen_level', 'medium')}, Phosphorus: {raw_soil.get('phosphorus_level', 'medium')}, Potassium: {raw_soil.get('potassium_level', 'medium')}.",
        "drainage_assessment": f"Drainage quality is {drainage}.",
        "key_issues": issues if issues else ["No major soil issues detected."],
        "amendments": amendments if amendments else ["Continue standard crop rotation and compost additions."],
        "soil_strengths": strengths,
        "confidence": 0.5,
    }


