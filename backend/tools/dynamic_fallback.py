"""
Dynamic Rule-Based Fallback Generator.
Generates tailored agronomic advice based on actual weather data and soil profile
when the Gemini API is unavailable (quota exceeded/429 limits).
"""

from typing import Any

def generate_dynamic_fallback(
    location: str,
    crop_type: str,
    farming_goal: str,
    weather_data: dict[str, Any],
    soil_data: dict[str, Any]
) -> dict[str, Any]:
    # 1. Determine weather risks dynamically
    temp_max = weather_data.get("temperature_max_c") or 25.0
    temp_min = weather_data.get("temperature_min_c") or 15.0
    precip = weather_data.get("total_precipitation_mm") or 0.0
    wind = weather_data.get("max_wind_speed_kmh") or 10.0
    severe_risk = str(weather_data.get("severe_weather_risk") or "LOW").upper()

    weather_risks = []
    weather_precautions = []
    weather_fav = []

    # Risk analysis
    if temp_max > 38.0:
        weather_risks.append("Extreme heat stress hazard")
        weather_precautions.append("Increase irrigation frequency during cooler early morning hours")
    elif temp_max > 32.0:
        weather_risks.append("Moderate heat stress")
        weather_precautions.append("Monitor soil moisture closely; apply mulch to reduce evaporation")
    else:
        weather_fav.append("Temperatures are in the optimal range for plant growth")

    if temp_min < 5.0:
        weather_risks.append("Frost hazard / chilling injury risk")
        weather_precautions.append("Cover vulnerable seedlings or apply light overnight irrigation to protect foliage")

    if precip > 40.0:
        weather_risks.append("Heavy rainfall and potential waterlogging risk")
        weather_precautions.append("Clear drainage channels; suspend active irrigation cycles immediately")
    elif precip > 15.0:
        weather_fav.append("Beneficial rainfall expected to supplement soil moisture")
    else:
        weather_risks.append("Minimal precipitation; dry conditions expected")
        weather_precautions.append("Maintain standard scheduled irrigation cycles")

    if wind > 25.0:
        weather_risks.append("High wind speeds; risk of crop lodging or wind damage")
        weather_precautions.append("Check stakes/supports; delay pesticide applications to avoid drift")

    overall_weather_risk = "LOW"
    if severe_risk == "HIGH" or temp_max > 38.0 or precip > 40.0:
        overall_weather_risk = "HIGH"
    elif severe_risk == "EXTREME":
        overall_weather_risk = "EXTREME"
    elif temp_max > 32.0 or precip > 15.0 or wind > 20.0:
        overall_weather_risk = "MODERATE"

    # 2. Determine soil assessment dynamically
    soil_type = soil_data.get("soil_type") or "Loam"
    ph_str = soil_data.get("ph_range") or "6.0–7.0"
    drainage = str(soil_data.get("drainage_quality") or "moderate").lower()
    fertility = str(soil_data.get("fertility_rating") or "medium").lower()
    salinity = str(soil_data.get("salinity_risk") or "low").lower()

    # pH parsing
    ph_val = 6.5
    try:
        if "–" in ph_str:
            parts = ph_str.split("–")
            ph_val = (float(parts[0]) + float(parts[1])) / 2
        elif "-" in ph_str:
            parts = ph_str.split("-")
            ph_val = (float(parts[0]) + float(parts[1])) / 2
        else:
            ph_val = float(ph_str)
    except Exception:
        pass

    soil_issues = []
    soil_amendments = []
    soil_strengths = [f"Established soil type is {soil_type}"]

    if ph_val < 5.5:
        soil_issues.append("High soil acidity; risk of nutrient lockout")
        soil_amendments.append("Apply agricultural lime (calcium carbonate) or dolomite to raise soil pH")
    elif ph_val > 7.8:
        soil_issues.append("High soil alkalinity; restricts micronutrient uptake")
        soil_amendments.append("Incorporate elemental sulfur or acidic organic mulch (e.g. pine needles) to lower pH")
    else:
        soil_strengths.append(f"Soil pH ({ph_str}) is in the optimal range")

    if drainage == "poor":
        soil_issues.append("Poor soil drainage; high susceptibility to root rot")
        soil_amendments.append("Install raised beds or deep drainage ditches; avoid compacting the soil")
    elif drainage == "excessive":
        soil_issues.append("Excessive soil drainage; low water retention capacity")
        soil_amendments.append("Incorporate well-rotted manure or compost to improve water-holding capacity")
    else:
        soil_strengths.append("Soil exhibits good water-drainage and aeration qualities")

    if fertility == "low":
        soil_issues.append("Low general soil fertility and nutrient levels")
        soil_amendments.append("Apply NPK balanced organic fertilizer and inoculate with mycorrhizal fungi")
    else:
        soil_strengths.append(f"Soil fertility level is rated as {fertility}")

    if salinity == "moderate" or salinity == "high":
        soil_issues.append("Elevated salinity risk; potential osmotic stress")
        soil_amendments.append("Leach excess salts with high-quality water; avoid saline groundwater irrigation")

    # 3. Formulate Crop Action Plan dynamically
    crop_lower = crop_type.lower()
    goal_lower = farming_goal.lower()

    # Irrigation planning
    if "water" in goal_lower or "conservation" in goal_lower:
        if drainage == "poor":
            irrigation_plan = "Implement controlled alternate wetting and drying (AWD) to save water and prevent root rot."
        elif drainage == "excessive":
            irrigation_plan = "Deploy drip irrigation with frequent short cycles coupled with organic mulching to prevent run-off."
        else:
            irrigation_plan = "Use micro-drip irrigation scheduled exclusively for early morning hours to minimize evaporative losses."
    else:
        if drainage == "poor":
            irrigation_plan = "Irrigate cautiously, letting the topsoil dry out slightly before the next application."
        else:
            irrigation_plan = "Maintain consistent moisture levels based on crop demands, checking moisture depth daily."

    # Fertilizer planning
    if fertility == "low":
        fertilizer_plan = "Apply split-dose nitrogen fertilizer (3 splits) with base organic compost to prevent leaching."
    elif ph_val < 5.5:
        fertilizer_plan = "Avoid ammonium fertilizers; use nitrate-based options and add calcium-magnesium amendments."
    else:
        fertilizer_plan = "Apply standard NPK mix customized for crop vegetation cycles; supplement with zinc/iron foliar sprays."

    # Weekly schedule based on crop
    weekly_schedules = {
        "wheat": {
            "week_1": {"focus": "Germination & Irrigation Control", "tasks": ["Ensure light irrigation to support crown root initiation (CRI)", "Monitor seedling emergence uniformity"]},
            "week_2": {"focus": "Weeding & Nutrient Administration", "tasks": ["Perform primary manual weeding or apply post-emergence herbicide", "Apply the first split of nitrogen fertilizer"]},
            "week_3": {"focus": "Tillering & Moisture Monitoring", "tasks": ["Maintain soil moisture at 30-35% field capacity", "Inspect crops for early signs of rust infection"]},
            "week_4": {"focus": "Jointing Stage Maintenance", "tasks": ["Apply secondary irrigation cycle if dry weather persists", "Assess stem strength and check for nutrient deficiencies"]}
        },
        "rice": {
            "week_1": {"focus": "Paddy Flooding & Transplanting", "tasks": ["Maintain a shallow water layer of 2-3 cm in the field", "Monitor transplanting shock recovery"]},
            "week_2": {"focus": "Water Level Management", "tasks": ["Implement alternate wetting and drying (AWD) water conservation protocol", "Check for early signs of blast disease"]},
            "week_3": {"focus": "Weed Control & Nitrogen Application", "tasks": ["Apply standard herbicide or perform manual interculture weeding", "Apply top dressing of urea fertilizer"]},
            "week_4": {"focus": "Tillering & Pest Scouter", "tasks": ["Gradually increase water level to 5 cm as tillering advances", "Install pheromone traps for stem borer detection"]}
        },
        "cotton": {
            "week_1": {"focus": "Seedling Care & Thinning", "tasks": ["Thin seedlings to maintain optimal spacing between plants", "Check soil moisture levels around root zones"]},
            "week_2": {"focus": "Foliar Fertilization", "tasks": ["Apply nitrogen-rich foliar sprays to boost leafy growth", "Perform shallow hoeing to break crust and aerate roots"]},
            "week_3": {"focus": "Pest Monitoring", "tasks": ["Scout fields for aphids, whiteflies, and bollworms", "Set up sticky yellow traps around field borders"]},
            "week_4": {"focus": "Squaring Management", "tasks": ["Apply boron and magnesium supplements to support boll development", "Regulate drip irrigation to avoid excessive vegetative growth"]}
        }
    }

    # Fallback weekly schedule if crop not in list
    default_schedule = {
        "week_1": {"focus": "Initial Crop Care", "tasks": [f"Conduct crop inspection and soil moisture check for {crop_type}", "Ensure weed-free environment around seedlings"]},
        "week_2": {"focus": "Nutrient Boost", "tasks": ["Apply first organic fertilizer application to support vegetative growth", "Verify irrigation system operation and flow rate"]},
        "week_3": {"focus": "Pest & Disease Monitoring", "tasks": ["Scout foliage daily for signs of fungal or insect infestation", "Clean field borders and irrigation pathways"]},
        "week_4": {"focus": "Maintenance & Assessment", "tasks": ["Monitor crop vigor and leaf color", "Document soil moisture status and adjust watering intervals"]}
    }

    weekly_schedule = weekly_schedules.get(crop_lower, default_schedule)

    pest_disease_watch = []
    if crop_lower == "wheat":
        pest_disease_watch = ["Yellow Rust", "Aphids", "Root Rot"]
    elif crop_lower == "rice":
        pest_disease_watch = ["Rice Blast", "Brown Planthopper", "Stem Borer"]
    elif crop_lower == "cotton":
        pest_disease_watch = ["Bollworms", "Whiteflies", "Damping Off"]
    else:
        pest_disease_watch = ["Fungal Leaf Spot", "Aphids", "Cutworms"]

    return {
        "overall_assessment": f"Rule-based action plan for {crop_type} in {location} compiled successfully using local sensor and regional profiles. This response has been automatically generated due to API rate limit limits, ensuring full offline reliability.",
        "risk_level": overall_weather_risk,
        "confidence": 0.50,
        "immediate_actions": [
            f"Set irrigation parameters to align with: {irrigation_plan}",
            f"Review amendment protocol: {', '.join(soil_amendments) if soil_amendments else 'None required'}"
        ],
        "weekly_schedule": weekly_schedule,
        "irrigation_plan": irrigation_plan,
        "fertilizer_plan": fertilizer_plan,
        "pest_disease_watch": pest_disease_watch,
        "climate_adaptation_tips": [
            "Incorporate high-quality organic matter into the soil to improve overall resilience.",
            "Utilize localized weather forecasts to delay active pesticide applications when high winds are predicted.",
            "Use mulch covers to regulate soil temperature extremes."
        ]
    }
