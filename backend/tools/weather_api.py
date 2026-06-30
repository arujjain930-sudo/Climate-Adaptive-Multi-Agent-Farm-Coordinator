"""
Weather tool adapter — Open-Meteo + Nominatim geocoding.

Architecture notes:
  • Nominatim converts a human location name (e.g. "Punjab, India") into
    lat/lon coordinates.  Open-Meteo then returns a 7-day forecast for
    those coordinates.
  • Both APIs are free and require no API key.
  • If either API call fails we return clearly-labelled fallback data so
    the pipeline can still produce useful (if less precise) advice.
  • All HTTP calls use httpx with a 10-second timeout.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

import httpx

logger = logging.getLogger("farm_coordinator.weather_api")

# ── Constants ────────────────────────────────────────────────────────────
_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
_TIMEOUT = 10.0  # seconds
_USER_AGENT = "ClimateFarmCoordinator/1.0"  # Nominatim requires a UA


# ── Fallback Data ────────────────────────────────────────────────────────
# Used when the API is unreachable so the pipeline doesn't break.
_FALLBACK_WEATHER: dict[str, Any] = {
    "source": "fallback_defaults",
    "note": "Live weather data unavailable — using regional estimates.",
    "location_resolved": "Unknown",
    "latitude": 0.0,
    "longitude": 0.0,
    "temperature_avg_c": 28.0,
    "temperature_max_c": 34.0,
    "temperature_min_c": 22.0,
    "relative_humidity_avg_pct": 65.0,
    "total_precipitation_mm": 12.0,
    "max_wind_speed_kmh": 15.0,
    "dominant_wind_direction_deg": 180,
    "severe_weather_risk": "UNKNOWN",
    "forecast_days": 7,
    "daily_summary": [],
}


# ── Public Interface ─────────────────────────────────────────────────────

async def fetch_weather(location: str) -> dict[str, Any]:
    """
    Fetch a 7-day weather forecast for *location*.

    Steps:
      1. Geocode the location name → (lat, lon).
      2. Hit Open-Meteo for daily forecast data.
      3. Derive a severe-weather risk label.

    Returns a flat dict of weather metrics for downstream agents.
    """
    try:
        lat, lon, resolved_name = await _geocode(location)
        weather = await _fetch_open_meteo(lat, lon)
        weather["location_resolved"] = resolved_name
        weather["latitude"] = lat
        weather["longitude"] = lon
        weather["source"] = "open_meteo_live"
        return weather
    except Exception as exc:
        logger.warning("Weather fetch failed for '%s': %s — using fallback", location, exc)
        fallback = dict(_FALLBACK_WEATHER)
        fallback["location_resolved"] = location
        return fallback


# ── Internal Helpers ─────────────────────────────────────────────────────

async def _geocode(location: str) -> tuple[float, float, str]:
    """
    Convert a human-readable location to (latitude, longitude, display_name).

    Uses the Nominatim free geocoding API (rate-limited to 1 req/sec by OSM
    policy — acceptable for our low-traffic backend).
    """
    params = {
        "q": location,
        "format": "json",
        "limit": 1,
    }
    headers = {"User-Agent": _USER_AGENT}

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(_NOMINATIM_URL, params=params, headers=headers)
        resp.raise_for_status()
        results = resp.json()

    if not results:
        raise ValueError(f"Geocoding returned no results for '{location}'")

    hit = results[0]
    return float(hit["lat"]), float(hit["lon"]), hit.get("display_name", location)


async def _fetch_open_meteo(lat: float, lon: float) -> dict[str, Any]:
    """
    Pull a 7-day daily forecast from the Open-Meteo API.

    Returns a dict with aggregated and daily-level weather data plus a
    computed severe-weather risk label.
    """
    today = date.today()
    end_date = today + timedelta(days=6)

    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": ",".join([
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_sum",
            "windspeed_10m_max",
            "winddirection_10m_dominant",
            "relative_humidity_2m_mean",
        ]),
        "start_date": today.isoformat(),
        "end_date": end_date.isoformat(),
        "timezone": "auto",
    }

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(_OPEN_METEO_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    daily = data.get("daily", {})

    # ── Safely extract arrays with fallbacks ────────────────────────
    temps_max = daily.get("temperature_2m_max") or [30.0]
    temps_min = daily.get("temperature_2m_min") or [20.0]
    precip = daily.get("precipitation_sum") or [0.0]
    wind = daily.get("windspeed_10m_max") or [10.0]
    wind_dir = daily.get("winddirection_10m_dominant") or [180]
    humidity = daily.get("relative_humidity_2m_mean") or [60.0]
    dates = daily.get("time") or []

    # Replace None values that the API sometimes returns
    temps_max = [v if v is not None else 30.0 for v in temps_max]
    temps_min = [v if v is not None else 20.0 for v in temps_min]
    precip = [v if v is not None else 0.0 for v in precip]
    wind = [v if v is not None else 10.0 for v in wind]
    wind_dir = [v if v is not None else 180 for v in wind_dir]
    humidity = [v if v is not None else 60.0 for v in humidity]

    # ── Aggregate metrics ───────────────────────────────────────────
    avg_temp = round(sum(t for t in temps_max) / len(temps_max), 1) if temps_max else 28.0
    max_temp = max(temps_max) if temps_max else 34.0
    min_temp = min(temps_min) if temps_min else 22.0
    total_rain = round(sum(precip), 1)
    max_wind = max(wind) if wind else 15.0
    avg_humidity = round(sum(humidity) / len(humidity), 1) if humidity else 65.0
    dominant_dir = int(wind_dir[0]) if wind_dir else 180

    # ── Severe weather risk classification ──────────────────────────
    risk = _classify_risk(max_temp, min_temp, total_rain, max_wind)

    # ── Daily breakdown for detailed analysis ───────────────────────
    daily_summary = []
    for i in range(len(dates)):
        daily_summary.append({
            "date": dates[i] if i < len(dates) else f"day_{i+1}",
            "temp_max_c": temps_max[i] if i < len(temps_max) else None,
            "temp_min_c": temps_min[i] if i < len(temps_min) else None,
            "precipitation_mm": precip[i] if i < len(precip) else None,
            "wind_max_kmh": wind[i] if i < len(wind) else None,
            "humidity_pct": humidity[i] if i < len(humidity) else None,
        })

    return {
        "temperature_avg_c": avg_temp,
        "temperature_max_c": max_temp,
        "temperature_min_c": min_temp,
        "relative_humidity_avg_pct": avg_humidity,
        "total_precipitation_mm": total_rain,
        "max_wind_speed_kmh": max_wind,
        "dominant_wind_direction_deg": dominant_dir,
        "severe_weather_risk": risk,
        "forecast_days": len(dates),
        "daily_summary": daily_summary,
    }


def _classify_risk(
    max_temp: float,
    min_temp: float,
    total_rain: float,
    max_wind: float,
) -> str:
    """
    Heuristic risk label based on 7-day forecast aggregates.

    Categories: LOW, MODERATE, HIGH, EXTREME
    """
    score = 0

    # Heat stress
    if max_temp > 42:
        score += 3
    elif max_temp > 38:
        score += 2
    elif max_temp > 35:
        score += 1

    # Frost risk
    if min_temp < 0:
        score += 3
    elif min_temp < 4:
        score += 2

    # Flood / waterlogging
    if total_rain > 150:
        score += 3
    elif total_rain > 80:
        score += 2
    elif total_rain > 40:
        score += 1

    # Wind damage
    if max_wind > 80:
        score += 3
    elif max_wind > 50:
        score += 2
    elif max_wind > 30:
        score += 1

    if score >= 6:
        return "EXTREME"
    elif score >= 4:
        return "HIGH"
    elif score >= 2:
        return "MODERATE"
    return "LOW"
