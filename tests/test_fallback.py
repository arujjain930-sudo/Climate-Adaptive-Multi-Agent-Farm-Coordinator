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

def test_parse_json_response_verifies_dict():
    # Test that parse_json_response returns fallback if JSON is valid but not a dict (e.g. list, string)
    agent = WeatherAnalystAgent()
    fallback = {"custom": "fallback"}
    
    # 1. Direct parse is a list
    res = agent.parse_json_response("[1, 2, 3]", fallback=fallback)
    assert res == fallback
    
    # 2. Markdown fence is a list
    res = agent.parse_json_response("```json\n[1, 2, 3]\n```", fallback=fallback)
    assert res == fallback

    # 3. Direct parse is a dict (should succeed)
    res = agent.parse_json_response('{"foo": "bar"}', fallback=fallback)
    assert res == {"foo": "bar"}

@pytest.mark.asyncio
async def test_weather_agent_fatal_exception_handling():
    # Force run method to fail before call_gemini (e.g., fetch_weather raises TypeError)
    with patch("backend.agents.weather_agent.fetch_weather", side_effect=TypeError("Unexpected Type Error")):
        agent = WeatherAnalystAgent()
        result = await agent.run(location="Pune, India", crop_type="Rice")
        # Should gracefully return a fallback dict and not raise the TypeError
        assert result["raw_weather"]["source"] == "fatal_fallback"
        assert "error" in result["analysis"]
        assert "Fatal run exception" in result["analysis"]["error"]
        assert result["analysis"]["confidence"] == 0.0

@pytest.mark.asyncio
async def test_soil_agent_fatal_exception_handling():
    # Force run method to fail before call_gemini (e.g., get_soil_profile raises KeyError)
    with patch("backend.agents.soil_agent.get_soil_profile", side_effect=KeyError("Missing Key")):
        agent = SoilParameterAgent()
        result = await agent.run(location="Pune, India", crop_type="Rice")
        # Should gracefully return a fallback dict and not raise the KeyError
        assert result["raw_soil"]["match_quality"] == "global_default"
        assert "error" in result["analysis"]
        assert "Fatal run exception" in result["analysis"]["error"]
        assert result["analysis"]["confidence"] == 0.0

@pytest.mark.asyncio
async def test_crop_agent_fatal_exception_handling():
    # Force run/refine method to fail by having json.dumps throw a ValueError
    with patch("json.dumps", side_effect=ValueError("Formatting error")):
        agent = CropActionAgent()
        result = await agent.run(
            location="Pune, India",
            crop_type="Rice",
            farming_goal="Water Conservation",
            notes="",
            weather_summary={"overall_risk": "LOW"},
            soil_summary={"ph_range": "6.0–7.5", "soil_type": "Loam"}
        )
        assert "error" in result["plan"]
        assert "Fatal run exception" in result["plan"]["error"]
        assert result["plan"]["confidence"] == 0.0
