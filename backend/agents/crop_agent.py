"""
Crop Action Agent — synthesises weather + soil analyses into an actionable plan.

Responsibility:
  1. Receive the weather and soil analysis summaries.
  2. Call Gemini with the combined context + farmer's goal.
  3. Return a structured, week-by-week farming action plan.
  4. Support a refinement call if the orchestrator requests one.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from backend.agents.base_agent import BaseAgent
from backend.prompts.templates import CROP_ACTION_PROMPT, CROP_ACTION_REFINEMENT_PROMPT
from backend.tools.dynamic_fallback import generate_dynamic_fallback

logger = logging.getLogger("farm_coordinator.crop_agent")


class CropActionAgent(BaseAgent):
    """Combines weather + soil data → generates an actionable farming plan."""

    agent_name = "CropActionAgent"

    async def run(
        self,
        *,
        location: str,
        crop_type: str,
        farming_goal: str,
        notes: str,
        weather_summary: dict[str, Any],
        soil_summary: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Generate the initial crop action plan.

        Returns a dict with:
          - ``plan``: the structured farming action plan
        """
        raw_weather = kwargs.get("raw_weather", weather_summary)
        raw_soil = kwargs.get("raw_soil", soil_summary)
        try:
            prompt = CROP_ACTION_PROMPT.format(
                location=location,
                crop_type=crop_type,
                farming_goal=farming_goal,
                notes=notes or "None",
                weather_summary=json.dumps(weather_summary, indent=2, default=str),
                soil_summary=json.dumps(soil_summary, indent=2, default=str),
            )

            try:
                raw_response = await self.call_gemini(prompt)
                local_fallback = None
                if raw_weather and raw_soil:
                    local_fallback = generate_dynamic_fallback(
                        location=location,
                        crop_type=crop_type,
                        farming_goal=farming_goal,
                        weather_data=raw_weather,
                        soil_data=raw_soil
                    )
                plan = self.parse_json_response(raw_response, fallback=local_fallback)
            except Exception as exc:
                logger.error("[%s] Gemini plan generation failed: %s", self.agent_name, exc)
                plan = generate_dynamic_fallback(
                    location=location,
                    crop_type=crop_type,
                    farming_goal=farming_goal,
                    weather_data=raw_weather,
                    soil_data=raw_soil
                )
                plan["error"] = str(exc)
                plan["confidence"] = 0.5
        except Exception as exc:
            logger.error("[%s] CropActionAgent run encountered an error: %s", self.agent_name, exc)
            plan = generate_dynamic_fallback(
                location=location,
                crop_type=crop_type,
                farming_goal=farming_goal,
                weather_data=raw_weather,
                soil_data=raw_soil
            )
            plan["error"] = f"Fatal run exception: {exc}"
            plan["confidence"] = 0.0

        # Ensure required keys exist
        if "confidence" not in plan:
            plan["confidence"] = 0.5
        if "risk_level" not in plan:
            plan["risk_level"] = "UNKNOWN"

        return {"plan": plan}

    async def refine(
        self,
        *,
        location: str,
        crop_type: str,
        farming_goal: str,
        notes: str,
        weather_summary: dict[str, Any],
        soil_summary: dict[str, Any],
        previous_output: dict[str, Any],
        issue_reason: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Re-run the crop action plan with extra refinement instructions.

        Called by the orchestrator when confidence is below threshold
        or risk is HIGH/EXTREME, to produce more specific recommendations.
        """
        raw_weather = kwargs.get("raw_weather", weather_summary)
        raw_soil = kwargs.get("raw_soil", soil_summary)
        try:
            prompt = CROP_ACTION_REFINEMENT_PROMPT.format(
                location=location,
                crop_type=crop_type,
                farming_goal=farming_goal,
                notes=notes or "None",
                weather_summary=json.dumps(weather_summary, indent=2, default=str),
                soil_summary=json.dumps(soil_summary, indent=2, default=str),
                previous_output=json.dumps(previous_output, indent=2, default=str),
                issue_reason=issue_reason,
            )

            raw_response = await self.call_gemini(prompt)
            local_fallback = None
            if raw_weather and raw_soil:
                local_fallback = generate_dynamic_fallback(
                    location=location,
                    crop_type=crop_type,
                    farming_goal=farming_goal,
                    weather_data=raw_weather,
                    soil_data=raw_soil
                )
            plan = self.parse_json_response(raw_response, fallback=local_fallback)
        except Exception as exc:
            logger.error("[%s] CropActionAgent refine encountered an error: %s", self.agent_name, exc)
            plan = generate_dynamic_fallback(
                location=location,
                crop_type=crop_type,
                farming_goal=farming_goal,
                weather_data=raw_weather,
                soil_data=raw_soil
            )
            plan["error"] = str(exc)

        if "confidence" not in plan:
            plan["confidence"] = 0.5
        if "risk_level" not in plan:
            plan["risk_level"] = "UNKNOWN"

        return {"plan": plan, "refined": True}

