"""
Orchestrator — coordinates the multi-agent pipeline.

Architecture:
  ┌──────────────┐     ┌──────────────┐
  │ WeatherAgent │     │  SoilAgent   │    ← run IN PARALLEL (asyncio.gather)
  └──────┬───────┘     └──────┬───────┘
         │                    │
         └──────┬─────────────┘
                ▼
         ┌──────────────┐
         │  CropAction  │    ← synthesises plan from both analyses
         │    Agent     │
         └──────┬───────┘
                │
           confidence < threshold
           OR risk HIGH/EXTREME ?
                │
           ┌────▼────┐
           │ Refine  │    ← max 2 iterations
           └─────────┘

Key design decisions:
  • Weather and Soil agents have no dependency on each other, so we
    run them concurrently to halve latency.
  • The refinement loop is capped at max_refinement_iterations (default 2)
    to prevent runaway API costs.
  • Every step records a timestamp so the frontend can show execution time.
"""

from __future__ import annotations

import asyncio
import copy
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any

from backend.agents.weather_agent import WeatherAnalystAgent
from backend.agents.soil_agent import SoilParameterAgent
from backend.agents.crop_agent import CropActionAgent
from backend.config import get_settings

logger = logging.getLogger("farm_coordinator.orchestrator")

# Simple in-memory cache: (location, crop_type, farming_goal) -> (timestamp, result_dict)
_pipeline_cache: dict[tuple[str, str, str], tuple[datetime, dict[str, Any]]] = {}


async def run_pipeline(
    *,
    location: str,
    crop_type: str,
    farming_goal: str,
    notes: str,
) -> dict[str, Any]:
    """
    Execute the full multi-agent pipeline and return the combined result.

    Parameters are expected to be already validated and sanitised.

    Returns a dict with:
      - timestamps for each step
      - raw + analysed weather data
      - raw + analysed soil data
      - the crop action plan (possibly refined)
      - metadata (iteration count, refinement reasons)
    """
    # ── Cache Check ──────────────────────────────────────────────────────────
    cache_key = (
        location.strip().lower(),
        crop_type.strip().lower(),
        farming_goal.strip().lower(),
    )
    now_time = datetime.now(timezone.utc)
    if cache_key in _pipeline_cache:
        cached_time, cached_result = _pipeline_cache[cache_key]
        if now_time - cached_time < timedelta(minutes=10):
            logger.info("Cache hit for location='%s', crop_type='%s', farming_goal='%s'. Returning cached result.", location, crop_type, farming_goal)
            cached_result_copy = copy.deepcopy(cached_result)
            if "input" in cached_result_copy:
                cached_result_copy["input"]["notes"] = notes
            return cached_result_copy
        else:
            _pipeline_cache.pop(cache_key, None)

    settings = get_settings()
    result: dict[str, Any] = {
        "request": {
            "location": location,
            "crop_type": crop_type,
            "farming_goal": farming_goal,
            "notes": notes,
        },
        "timestamps": {},
        "metadata": {
            "model": settings.gemini_model,
            "refinement_iterations": 0,
            "refinement_reasons": [],
        },
    }

    pipeline_start = _now()
    result["timestamps"]["pipeline_start"] = pipeline_start

    # ── Step 1: Run Weather + Soil agents in parallel ────────────────
    weather_agent = WeatherAnalystAgent()
    soil_agent = SoilParameterAgent()

    parallel_start = _now()
    result["timestamps"]["parallel_start"] = parallel_start

    logger.info("Starting Weather + Soil agents in parallel for '%s' / '%s'", location, crop_type)

    weather_result, soil_result = await asyncio.gather(
        weather_agent.run(location=location, crop_type=crop_type),
        soil_agent.run(location=location, crop_type=crop_type),
    )

    parallel_end = _now()
    result["timestamps"]["parallel_end"] = parallel_end
    logger.info("Parallel agents completed in %.1fs", _elapsed(parallel_start, parallel_end))

    result["weather"] = weather_result
    result["soil"] = soil_result

    # ── Step 2: Run Crop Action Agent ────────────────────────────────
    crop_agent = CropActionAgent()
    crop_start = _now()
    result["timestamps"]["crop_agent_start"] = crop_start

    crop_result = await crop_agent.run(
        location=location,
        crop_type=crop_type,
        farming_goal=farming_goal,
        notes=notes,
        weather_summary=weather_result.get("analysis", {}),
        soil_summary=soil_result.get("analysis", {}),
        raw_weather=weather_result.get("raw_weather", {}),
        raw_soil=soil_result.get("raw_soil", {}),
    )

    crop_end = _now()
    result["timestamps"]["crop_agent_end"] = crop_end

    plan = crop_result.get("plan", {})
    result["crop_plan"] = plan

    # ── Step 3: Refinement loop ──────────────────────────────────────
    # Re-run the Crop Action Agent if confidence is low or risk is high.
    # On serverless platforms (Vercel), skip refinement to stay within timeout.
    is_serverless = bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
    max_refine = 0 if is_serverless else settings.max_refinement_iterations
    iteration = 0
    while iteration < max_refine:
        needs_refinement, reason = _needs_refinement(plan, settings.confidence_threshold)
        if not needs_refinement:
            break

        iteration += 1
        logger.info(
            "Refinement iteration %d — reason: %s", iteration, reason
        )
        result["metadata"]["refinement_iterations"] = iteration
        result["metadata"]["refinement_reasons"].append(reason)

        refine_start = _now()
        result["timestamps"][f"refinement_{iteration}_start"] = refine_start

        refined_result = await crop_agent.refine(
            location=location,
            crop_type=crop_type,
            farming_goal=farming_goal,
            notes=notes,
            weather_summary=weather_result.get("analysis", {}),
            soil_summary=soil_result.get("analysis", {}),
            previous_output=plan,
            issue_reason=reason,
            raw_weather=weather_result.get("raw_weather", {}),
            raw_soil=soil_result.get("raw_soil", {}),
        )

        refine_end = _now()
        result["timestamps"][f"refinement_{iteration}_end"] = refine_end

        # Replace the plan with the refined version
        plan = refined_result.get("plan", plan)
        result["crop_plan"] = plan

    # ── Finalise ─────────────────────────────────────────────────────
    pipeline_end = _now()
    result["timestamps"]["pipeline_end"] = pipeline_end
    result["metadata"]["total_time_seconds"] = round(_elapsed(pipeline_start, pipeline_end), 2)

    logger.info(
        "Pipeline complete: %d refinement(s), %.1fs total",
        result["metadata"]["refinement_iterations"],
        result["metadata"]["total_time_seconds"],
    )

    # Add frontend-compatible top-level keys so the UI can display results
    final_response = _build_frontend_response(result)
    
    # Save to cache
    _pipeline_cache[cache_key] = (datetime.now(timezone.utc), final_response)
    
    return final_response


# ── Helpers ──────────────────────────────────────────────────────────────

def _needs_refinement(plan: dict[str, Any], threshold: float) -> tuple[bool, str]:
    """
    Decide whether the crop plan should be refined.

    Returns (should_refine, reason_string).
    """
    confidence = plan.get("confidence", 0.5)
    risk_level = str(plan.get("risk_level", "UNKNOWN")).upper()

    if confidence < threshold:
        return True, f"low confidence ({confidence:.2f} < {threshold:.2f})"

    if risk_level in ("HIGH", "EXTREME"):
        return True, f"risk level is {risk_level} — needs detailed contingency plans"

    return False, ""


def _now() -> str:
    """ISO-8601 timestamp in UTC."""
    return datetime.now(timezone.utc).isoformat()


def _elapsed(start_iso: str, end_iso: str) -> float:
    """Seconds between two ISO-8601 timestamps."""
    fmt = datetime.fromisoformat
    return (fmt(end_iso) - fmt(start_iso)).total_seconds()


def _build_frontend_response(result: dict[str, Any]) -> dict[str, Any]:
    """
    Format and structure the raw pipeline results into the exact keys
    and shape expected by the frontend (app.js).
    """
    crop_plan = result.get("crop_plan", {})
    weather_analysis = result.get("weather", {}).get("analysis", {})
    soil_analysis = result.get("soil", {}).get("analysis", {})
    request_data = result.get("request", {})

    # Extract risk level
    risk_level = (crop_plan.get("risk_level") or weather_analysis.get("overall_risk") or "MODERATE").upper()

    # Extract confidence (convert float 0-1 to percentage 0-100)
    raw_confidence = crop_plan.get("confidence") or weather_analysis.get("confidence") or 0.75
    if isinstance(raw_confidence, (int, float)):
        if raw_confidence <= 1.0:
            confidence_pct = int(raw_confidence * 100)
        else:
            confidence_pct = int(raw_confidence)
    else:
        confidence_pct = 75

    # Determine urgency
    urgency = "Normal"
    if risk_level == "EXTREME":
        urgency = "CRITICAL: Immediate Action Required"
    elif risk_level == "HIGH":
        urgency = "HIGH: Protective Measures Needed"
    elif risk_level == "MODERATE":
        urgency = "Moderate: Standard Monitoring"

    # Headline recommendation
    key_rec = "Follow the weekly crop protection and irrigation schedule."
    immediate = crop_plan.get("immediate_actions")
    if isinstance(immediate, list) and len(immediate) > 0:
        key_rec = str(immediate[0])

    return {
        "status": "success",
        "input": request_data,
        "summary": crop_plan.get("overall_assessment") or "Analysis completed successfully.",
        "risk_level": risk_level,
        "urgency": urgency,
        "confidence": confidence_pct,
        "key_recommendation": key_rec,
        "weather_analysis": weather_analysis,
        "soil_analysis": soil_analysis,
        "crop_action_plan": crop_plan,
        "schedule": crop_plan.get("weekly_schedule"),
        "timestamps": result.get("timestamps", {}),
        "metadata": result.get("metadata", {}),
    }

