"""
Weather Analyst Agent — fetches live weather data and interprets it with Gemini.

Responsibility:
  1. Call the weather tool adapter to get a 7-day forecast.
  2. Send the raw data + crop context to Gemini for interpretation.
  3. Return a structured risk summary.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from backend.agents.base_agent import BaseAgent
from backend.prompts.templates import WEATHER_ANALYSIS_PROMPT
from backend.tools.weather_api import fetch_weather

logger = logging.getLogger("farm_coordinator.weather_agent")


class WeatherAnalystAgent(BaseAgent):
    """Fetches weather forecast → interprets risk for a specific crop."""

    agent_name = "WeatherAnalystAgent"

    async def run(
        self,
        *,
        location: str,
        crop_type: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Execute the weather analysis pipeline.

        Returns a dict with:
          - ``raw_weather``: the data from the weather API / fallback
          - ``analysis``: Gemini's structured interpretation
        """
        # ── Step 1: Fetch weather data ──────────────────────────────
        logger.info("[%s] Fetching weather for '%s'", self.agent_name, location)
        raw_weather = await fetch_weather(location)

        # ── Step 2: Build prompt and call Gemini ────────────────────
        prompt = WEATHER_ANALYSIS_PROMPT.format(
            crop_type=crop_type,
            location=location,
            weather_data=json.dumps(raw_weather, indent=2, default=str),
        )

        try:
            raw_response = await self.call_gemini(prompt)
            # Create a localized fallback on the fly if parse fails
            local_fallback = get_dynamic_weather_fallback(location, crop_type, raw_weather)
            analysis = self.parse_json_response(raw_response, fallback=local_fallback)
        except Exception as exc:
            logger.error("[%s] Gemini interpretation failed: %s", self.agent_name, exc)
            analysis = get_dynamic_weather_fallback(location, crop_type, raw_weather)
            analysis["error"] = str(exc)

        # Ensure confidence key exists
        if "confidence" not in analysis:
            analysis["confidence"] = 0.5

        return {
            "raw_weather": raw_weather,
            "analysis": analysis,
        }

def get_dynamic_weather_fallback(location: str, crop_type: str, raw_weather: dict[str, Any]) -> dict[str, Any]:
    temp_max = raw_weather.get("temperature_max_c", 25.0)
    temp_min = raw_weather.get("temperature_min_c", 15.0)
    precip = raw_weather.get("total_precipitation_mm", 0.0)
    wind = raw_weather.get("max_wind_speed_kmh", 10.0)
    severe_risk = str(raw_weather.get("severe_weather_risk", "LOW")).upper()

    risks = []
    precautions = []
    fav = []

    if temp_max > 35.0:
        risks.append("High heat stress risk")
        precautions.append("Increase irrigation frequency")
    else:
        fav.append("Temperature is suitable for crop growth")

    if precip > 25.0:
        risks.append("Excessive precipitation / flooding hazard")
        precautions.append("Ensure field drainage pathways are clear")
    else:
        fav.append("Precipitation levels are moderate")

    if wind > 20.0:
        risks.append("High wind speeds")
        precautions.append("Delay spraying activities to avoid drift")

    overall_risk = "LOW"
    if severe_risk == "HIGH" or temp_max > 38.0 or precip > 40.0:
        overall_risk = "HIGH"
    elif severe_risk == "EXTREME":
        overall_risk = "EXTREME"
    elif temp_max > 32.0 or precip > 15.0 or wind > 15.0:
        overall_risk = "MODERATE"

    return {
        "overall_risk": overall_risk,
        "temperature_assessment": f"Max temp: {temp_max} C, Min temp: {temp_min} C.",
        "precipitation_assessment": f"Total expected precipitation: {precip} mm.",
        "wind_assessment": f"Expected peak wind speed: {wind} km/h.",
        "key_risks": risks if risks else ["No significant weather risks identified."],
        "precautions": precautions if precautions else ["Continue standard crop monitoring."],
        "favorable_conditions": fav,
        "confidence": 0.5,
    }
