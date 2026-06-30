"""
Prompt templates for each agent in the pipeline.

Design notes:
  • Each prompt is short and focused on a SINGLE task — this keeps Gemini
    responses more reliable and parseable.
  • We explicitly request JSON output with a defined schema so we can
    parse the response programmatically.
  • Variables are injected via str.format() / f-strings at call time.
  • The refinement prompt adds extra context from the previous iteration.
"""

from __future__ import annotations

# ── Weather Analyst Agent ────────────────────────────────────────────────

WEATHER_ANALYSIS_PROMPT = """\
Analyze this weather forecast for {crop_type} in {location}:
{weather_data}

Rules:
1. Return ONLY verified, authentic, and realistic agronomic recommendations.
2. Never generate exaggerated hazard warnings or speculative reports.
3. Do not include disclaimers or filler sentences (like "consult a local agronomist"). Rely strictly on the provided real-time weather and verified regional soil profiles.

Respond ONLY with this JSON schema:
{{
  "overall_risk": "LOW|MODERATE|HIGH|EXTREME",
  "temperature_assessment": "brief temperature impact assessment",
  "precipitation_assessment": "brief precipitation impact assessment",
  "wind_assessment": "brief wind impact assessment",
  "key_risks": ["risk"],
  "precautions": ["precaution"],
  "favorable_conditions": ["condition"],
  "confidence": 0.8
}}
"""

# ── Soil Parameter Agent ────────────────────────────────────────────────

SOIL_ANALYSIS_PROMPT = """\
Analyze this soil profile data for {crop_type} in {location} (match quality: {match_quality}):
{soil_data}

Rules:
1. Return ONLY verified, authentic, and realistic agronomic recommendations.
2. Never generate exaggerated hazard warnings or speculative reports.
3. Do not include disclaimers or filler sentences (like "consult a local agronomist"). Rely strictly on the provided real-time weather and verified regional soil profiles.

Respond ONLY with this JSON schema:
{{
  "suitability_rating": "excellent|good|moderate|poor",
  "ph_assessment": "brief pH suitability assessment",
  "nutrient_assessment": "brief NPK and organic matter assessment",
  "drainage_assessment": "brief drainage quality assessment",
  "key_issues": ["issue"],
  "amendments": ["amendment"],
  "soil_strengths": ["strength"],
  "confidence": 0.8
}}
"""

# ── Crop Action Agent ───────────────────────────────────────────────────

CROP_ACTION_PROMPT = """\
Create an action plan for {crop_type} in {location}. Goal: {farming_goal}. Notes: {notes}.
WEATHER: {weather_summary}
SOIL: {soil_summary}

Rules:
1. Return ONLY verified, authentic, and realistic agronomic recommendations.
2. Never generate exaggerated hazard warnings or speculative reports.
3. Do not include disclaimers or filler sentences (like "consult a local agronomist"). Rely strictly on the provided real-time weather and verified regional soil profiles.

Respond ONLY with this JSON schema:
{{
  "overall_assessment": "summary of conditions and outlook",
  "risk_level": "LOW|MODERATE|HIGH|EXTREME",
  "confidence": 0.8,
  "immediate_actions": ["immediate action task"],
  "weekly_schedule": {{
    "week_1": {{"focus": "focus area", "tasks": ["task1"]}},
    "week_2": {{"focus": "focus area", "tasks": ["task1"]}},
    "week_3": {{"focus": "focus area", "tasks": ["task1"]}},
    "week_4": {{"focus": "focus area", "tasks": ["task1"]}}
  }},
  "irrigation_plan": "irrigation advice",
  "fertilizer_plan": "fertilizer advice",
  "pest_disease_watch": ["pest/disease to watch"],
  "climate_adaptation_tips": ["climate adaptation advice"]
}}
"""

# ── Refinement Prompt (used when confidence is low or risk is high) ──────

CROP_ACTION_REFINEMENT_PROMPT = """\
Refine this action plan for {crop_type} in {location} due to {issue_reason}.
PREVIOUS: {previous_output}
Goal: {farming_goal}. Notes: {notes}.
WEATHER: {weather_summary}
SOIL: {soil_summary}

Provide more specific schedule details, quantities, and contingency plans.

Rules:
1. Return ONLY verified, authentic, and realistic agronomic recommendations.
2. Never generate exaggerated hazard warnings or speculative reports.
3. Do not include disclaimers or filler sentences (like "consult a local agronomist"). Rely strictly on the provided real-time weather and verified regional soil profiles.

Respond ONLY with this JSON schema:
{{
  "overall_assessment": "refined summary",
  "risk_level": "LOW|MODERATE|HIGH|EXTREME",
  "confidence": 0.9,
  "immediate_actions": ["specific immediate action"],
  "weekly_schedule": {{
    "week_1": {{"focus": "focus area", "tasks": ["specific task with quantities"]}},
    "week_2": {{"focus": "focus area", "tasks": ["specific task with quantities"]}},
    "week_3": {{"focus": "focus area", "tasks": ["specific task with quantities"]}},
    "week_4": {{"focus": "focus area", "tasks": ["specific task with quantities"]}}
  }},
  "irrigation_plan": "specific irrigation advice",
  "fertilizer_plan": "specific fertilizer advice",
  "pest_disease_watch": ["pest/disease watch details"],
  "climate_adaptation_tips": ["specific climate adaptation advice"],
  "contingency_plans": ["contingency step"]
}}
"""
