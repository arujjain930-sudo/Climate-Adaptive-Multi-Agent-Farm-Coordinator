import pytest
from unittest.mock import patch, AsyncMock
import httpx
from backend.tools.weather_api import fetch_weather
from backend.tools.soil_profiles import get_soil_profile
from backend.agents.weather_agent import WeatherAnalystAgent
from backend.agents.soil_agent import SoilParameterAgent
from backend.agents.crop_agent import CropActionAgent

@pytest.mark.asyncio
async def test_weather_api_failure_returns_fallback():
    # Force httpx to fail to simulate API down
    with patch("httpx.AsyncClient.get", side_effect=httpx.RequestError("API Down")):
        result = await fetch_weather("Pune, India")
        # Check that it returns fallback data cleanly rather than raising an exception
        assert result["source"] == "fallback_defaults"
        assert result["location_resolved"] == "Pune, India"
        assert result["temperature_avg_c"] == 28.0

def test_soil_profile_fallback_when_region_unknown():
    # If we pass an unknown location and crop, it should fallback to defaults
    profile = get_soil_profile("Unknown Mars Colony", "Space Potato")
    assert profile["match_quality"] == "global_default"
    assert profile["soil_type"] == "Loam (estimated)"  # standard global fallback
    assert profile["ph_range"] == "6.0–7.5"

@pytest.mark.asyncio
async def test_gemini_api_failure_weather_agent_fallback():
    # If Gemini raises an exception, the WeatherAnalystAgent should catch it and return fallback analysis
    with patch("backend.agents.base_agent.BaseAgent.call_gemini", side_effect=Exception("API Key Invalid")):
        agent = WeatherAnalystAgent()
        result = await agent.run(location="Pune, India", crop_type="Rice")
        
        # It should return fallback weather analysis
        assert result["analysis"]["overall_risk"] in ("LOW", "MODERATE", "HIGH", "EXTREME")
        assert "error" in result["analysis"]
        assert result["analysis"]["confidence"] == 0.5

@pytest.mark.asyncio
async def test_gemini_api_failure_soil_agent_fallback():
    # If Gemini raises an exception, the SoilParameterAgent should catch it and return fallback analysis
    with patch("backend.agents.base_agent.BaseAgent.call_gemini", side_effect=Exception("API Key Invalid")):
        agent = SoilParameterAgent()
        result = await agent.run(location="Pune, India", crop_type="Rice")
        
        assert result["analysis"]["suitability_rating"] in ("good", "moderate", "poor", "excellent")
        assert "error" in result["analysis"]
        assert result["analysis"]["confidence"] == 0.5

@pytest.mark.asyncio
async def test_gemini_api_failure_crop_agent_fallback():
    # If Gemini raises an exception, the CropActionAgent should catch it and return fallback plan
    with patch("backend.agents.base_agent.BaseAgent.call_gemini", side_effect=Exception("API Key Invalid")):
        agent = CropActionAgent()
        result = await agent.run(
            location="Pune, India",
            crop_type="Rice",
            farming_goal="Water Conservation",
            notes="",
            weather_summary={"overall_risk": "LOW"},
            soil_summary={"ph_range": "6.0–7.5", "soil_type": "Loam"}
        )
        
        assert result["plan"]["risk_level"] in ("LOW", "MODERATE", "HIGH", "EXTREME")
        assert "error" in result["plan"]
        assert result["plan"]["confidence"] == 0.5
