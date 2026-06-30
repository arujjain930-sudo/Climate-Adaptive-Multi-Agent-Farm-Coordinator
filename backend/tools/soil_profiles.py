"""
Rule-based soil profile tool.

Architecture notes:
  • We maintain a curated lookup table mapping (region, crop) pairs to
    typical soil parameters (pH, moisture, drainage, fertility, type).
  • When a user's location/crop matches a known profile we return that;
    otherwise we fall back through region-only → crop-only → global
    default.  This cascade means the pipeline ALWAYS has something to
    work with — the Gemini agent then interprets these values in context.
  • All data is synthetic / educational.  A production system would call
    a real soil API (e.g. ISRIC SoilGrids).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("farm_coordinator.soil_profiles")


# ── Soil Profile Database ────────────────────────────────────────────────
# Keys are (region_keyword, crop_keyword) tuples.  We match case-insensitively.

_PROFILES: dict[tuple[str, str], dict[str, Any]] = {
    # ── South Asia ───────────────────────────────────────────────────
    ("punjab", "wheat"): {
        "soil_type": "Alluvial loam",
        "ph_range": "6.5–7.8",
        "organic_matter_pct": 0.8,
        "nitrogen_level": "medium",
        "phosphorus_level": "medium",
        "potassium_level": "high",
        "moisture_pct": 35,
        "drainage_quality": "good",
        "fertility_rating": "high",
        "salinity_risk": "moderate",
        "notes": "Indo-Gangetic alluvial plains; wheat is well-suited.",
    },
    ("punjab", "rice"): {
        "soil_type": "Alluvial clay-loam",
        "ph_range": "6.0–7.5",
        "organic_matter_pct": 1.0,
        "nitrogen_level": "medium",
        "phosphorus_level": "low",
        "potassium_level": "medium",
        "moisture_pct": 55,
        "drainage_quality": "moderate",
        "fertility_rating": "high",
        "salinity_risk": "low",
        "notes": "Paddy soils in Punjab; needs good water management.",
    },
    ("kerala", "rice"): {
        "soil_type": "Laterite",
        "ph_range": "4.5–6.0",
        "organic_matter_pct": 2.5,
        "nitrogen_level": "high",
        "phosphorus_level": "low",
        "potassium_level": "medium",
        "moisture_pct": 60,
        "drainage_quality": "moderate",
        "fertility_rating": "medium",
        "salinity_risk": "low",
        "notes": "Acidic laterite soils; benefits from lime application.",
    },
    ("maharashtra", "cotton"): {
        "soil_type": "Black cotton soil (Vertisol)",
        "ph_range": "7.5–8.5",
        "organic_matter_pct": 0.6,
        "nitrogen_level": "low",
        "phosphorus_level": "medium",
        "potassium_level": "high",
        "moisture_pct": 40,
        "drainage_quality": "poor",
        "fertility_rating": "medium",
        "salinity_risk": "moderate",
        "notes": "Self-mulching black soil; cracks when dry, swells when wet.",
    },
    ("rajasthan", "millet"): {
        "soil_type": "Sandy arid",
        "ph_range": "7.0–8.5",
        "organic_matter_pct": 0.3,
        "nitrogen_level": "low",
        "phosphorus_level": "low",
        "potassium_level": "medium",
        "moisture_pct": 15,
        "drainage_quality": "excessive",
        "fertility_rating": "low",
        "salinity_risk": "high",
        "notes": "Arid sandy soils; millet is drought-tolerant and suitable.",
    },
    # ── Sub-Saharan Africa ───────────────────────────────────────────
    ("kenya", "maize"): {
        "soil_type": "Ferralsol (red tropical)",
        "ph_range": "5.0–6.5",
        "organic_matter_pct": 1.8,
        "nitrogen_level": "low",
        "phosphorus_level": "very low",
        "potassium_level": "medium",
        "moisture_pct": 30,
        "drainage_quality": "good",
        "fertility_rating": "medium",
        "salinity_risk": "low",
        "notes": "Deep, well-drained tropical soils; phosphorus fixation common.",
    },
    ("nigeria", "cassava"): {
        "soil_type": "Sandy loam",
        "ph_range": "5.5–6.5",
        "organic_matter_pct": 1.2,
        "nitrogen_level": "low",
        "phosphorus_level": "low",
        "potassium_level": "medium",
        "moisture_pct": 25,
        "drainage_quality": "good",
        "fertility_rating": "medium",
        "salinity_risk": "low",
        "notes": "Cassava tolerates poor soils but responds well to potassium.",
    },
    # ── Southeast Asia ───────────────────────────────────────────────
    ("thailand", "rice"): {
        "soil_type": "Alluvial clay",
        "ph_range": "5.5–7.0",
        "organic_matter_pct": 2.0,
        "nitrogen_level": "medium",
        "phosphorus_level": "medium",
        "potassium_level": "medium",
        "moisture_pct": 58,
        "drainage_quality": "poor",
        "fertility_rating": "high",
        "salinity_risk": "low",
        "notes": "Central plain alluvium; excellent for flooded rice.",
    },
    ("vietnam", "coffee"): {
        "soil_type": "Basaltic red soil",
        "ph_range": "4.5–5.5",
        "organic_matter_pct": 3.0,
        "nitrogen_level": "high",
        "phosphorus_level": "medium",
        "potassium_level": "high",
        "moisture_pct": 42,
        "drainage_quality": "good",
        "fertility_rating": "high",
        "salinity_risk": "low",
        "notes": "Central Highlands basalt; ideal for robusta coffee.",
    },
    # ── Americas ─────────────────────────────────────────────────────
    ("iowa", "corn"): {
        "soil_type": "Mollisol (prairie loam)",
        "ph_range": "6.0–7.0",
        "organic_matter_pct": 4.5,
        "nitrogen_level": "high",
        "phosphorus_level": "high",
        "potassium_level": "high",
        "moisture_pct": 38,
        "drainage_quality": "good",
        "fertility_rating": "very high",
        "salinity_risk": "low",
        "notes": "Some of the most productive agricultural soil on Earth.",
    },
    ("california", "grapes"): {
        "soil_type": "Sandy loam / alluvial",
        "ph_range": "6.0–7.5",
        "organic_matter_pct": 1.5,
        "nitrogen_level": "medium",
        "phosphorus_level": "medium",
        "potassium_level": "medium",
        "moisture_pct": 22,
        "drainage_quality": "good",
        "fertility_rating": "medium",
        "salinity_risk": "moderate",
        "notes": "Mediterranean climate; deficit irrigation common for wine grapes.",
    },
    ("brazil", "soybean"): {
        "soil_type": "Oxisol (Cerrado)",
        "ph_range": "4.5–5.5",
        "organic_matter_pct": 2.0,
        "nitrogen_level": "low",
        "phosphorus_level": "very low",
        "potassium_level": "low",
        "moisture_pct": 28,
        "drainage_quality": "good",
        "fertility_rating": "low",
        "salinity_risk": "low",
        "notes": "Acidic; requires heavy liming and P fertilization.",
    },
}

# ── Region-only fallbacks (when crop doesn't match) ──────────────────────
_REGION_DEFAULTS: dict[str, dict[str, Any]] = {
    "punjab": {
        "soil_type": "Alluvial loam",
        "ph_range": "6.5–7.5",
        "organic_matter_pct": 0.9,
        "nitrogen_level": "medium",
        "phosphorus_level": "medium",
        "potassium_level": "medium",
        "moisture_pct": 35,
        "drainage_quality": "good",
        "fertility_rating": "high",
        "salinity_risk": "moderate",
        "notes": "General alluvial profile for Indo-Gangetic plains.",
    },
    "india": {
        "soil_type": "Mixed alluvial",
        "ph_range": "6.0–8.0",
        "organic_matter_pct": 0.7,
        "nitrogen_level": "medium",
        "phosphorus_level": "low",
        "potassium_level": "medium",
        "moisture_pct": 32,
        "drainage_quality": "moderate",
        "fertility_rating": "medium",
        "salinity_risk": "moderate",
        "notes": "Average Indian soil profile; actual conditions vary widely.",
    },
    "africa": {
        "soil_type": "Tropical ferralsol",
        "ph_range": "5.0–6.5",
        "organic_matter_pct": 1.5,
        "nitrogen_level": "low",
        "phosphorus_level": "low",
        "potassium_level": "medium",
        "moisture_pct": 28,
        "drainage_quality": "good",
        "fertility_rating": "medium",
        "salinity_risk": "low",
        "notes": "Generic tropical soil profile.",
    },
    "usa": {
        "soil_type": "Temperate loam",
        "ph_range": "6.0–7.0",
        "organic_matter_pct": 3.0,
        "nitrogen_level": "medium",
        "phosphorus_level": "medium",
        "potassium_level": "medium",
        "moisture_pct": 35,
        "drainage_quality": "good",
        "fertility_rating": "high",
        "salinity_risk": "low",
        "notes": "General US temperate soil profile.",
    },
}

# ── Global fallback ──────────────────────────────────────────────────────
_GLOBAL_DEFAULT: dict[str, Any] = {
    "soil_type": "Loam (estimated)",
    "ph_range": "6.0–7.5",
    "organic_matter_pct": 1.5,
    "nitrogen_level": "medium",
    "phosphorus_level": "medium",
    "potassium_level": "medium",
    "moisture_pct": 30,
    "drainage_quality": "moderate",
    "fertility_rating": "medium",
    "salinity_risk": "low",
    "notes": "No specific soil data for this region/crop — using global estimates.",
}


# ── Public Interface ─────────────────────────────────────────────────────

def get_soil_profile(location: str, crop_type: str) -> dict[str, Any]:
    """
    Look up the best-matching soil profile for a (location, crop) pair.

    Search cascade:
      1. Exact (region_keyword, crop_keyword) match.
      2. Region-only match.
      3. Global default.

    Returns a dict with soil parameters and a 'match_quality' field
    indicating how specific the data is.
    """
    loc_lower = location.lower()
    crop_lower = crop_type.lower()

    # 1. Try exact (region, crop) match
    for (region_key, crop_key), profile in _PROFILES.items():
        if region_key in loc_lower and crop_key in crop_lower:
            logger.info("Exact soil match: (%s, %s)", region_key, crop_key)
            return {**profile, "match_quality": "exact", "matched_region": region_key, "matched_crop": crop_key}

    # 2. Try region-only match
    for region_key, profile in _REGION_DEFAULTS.items():
        if region_key in loc_lower:
            logger.info("Region-only soil match: %s", region_key)
            return {**profile, "match_quality": "region_only", "matched_region": region_key, "matched_crop": crop_type}

    # 2b. Also try region keys from the main profiles table
    for (region_key, _crop_key), profile in _PROFILES.items():
        if region_key in loc_lower:
            logger.info("Partial soil match via profiles: %s", region_key)
            return {**profile, "match_quality": "region_partial", "matched_region": region_key, "matched_crop": crop_type}

    # 3. Global fallback
    logger.info("No soil match — using global default for '%s' / '%s'", location, crop_type)
    return {**_GLOBAL_DEFAULT, "match_quality": "global_default", "matched_region": location, "matched_crop": crop_type}
