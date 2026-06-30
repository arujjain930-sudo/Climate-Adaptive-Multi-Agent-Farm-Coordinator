import pytest
import json
from unittest.mock import patch, AsyncMock
from backend.orchestrator import run_pipeline

@pytest.mark.asyncio
async def test_run_pipeline_success(mock_gemini_response):
    # Mock tool calls and Gemini calls
    mock_weather_raw = {
        "temperature_avg_c": 25.0,
        "temperature_max_c": 30.0,
        "temperature_min_c": 20.0,
        "relative_humidity_avg_pct": 70.0,
        "total_precipitation_mm": 5.0,
        "max_wind_speed_kmh": 10.0,
        "dominant_wind_direction_deg": 180,
        "severe_weather_risk": "LOW",
        "forecast_days": 7,
        "daily_summary": [],
        "source": "open_meteo_live",
        "location_resolved": "Pune, India"
    }
    
    mock_soil_raw = {
        "region": "default",
        "soil_type": "Loam",
        "ph": 6.5,
        "drainage": "Good",
        "moisture": "Moderate",
        "match_quality": "default_fallback"
    }

    with patch("backend.agents.weather_agent.fetch_weather", AsyncMock(return_value=mock_weather_raw)) as mock_weather_fetch, \
         patch("backend.agents.soil_agent.get_soil_profile", return_value=mock_soil_raw) as mock_soil_get:
         
        # We mock BaseAgent.call_gemini to return appropriate responses depending on who is calling it.
        # But to do that dynamically, we can use a side_effect function on a mocked method.
        async def mock_call_gemini_side_effect(prompt):
            if "analyze this weather forecast" in prompt.lower():
                return json.dumps(mock_gemini_response["weather_analyst"])
            elif "analyze this soil profile data" in prompt.lower():
                return json.dumps(mock_gemini_response["soil_parameter"])
            elif "create an action plan" in prompt.lower():
                return json.dumps(mock_gemini_response["crop_action"])
            return "{}"

        with patch("backend.agents.base_agent.BaseAgent.call_gemini", AsyncMock(side_effect=mock_call_gemini_side_effect)):
            result = await run_pipeline(
                location="Pune, India",
                crop_type="Rice",
                farming_goal="Water Conservation",
                notes="drip irrigation"
            )

            # Assertions on response structure
            assert result["status"] == "success"
            assert result["input"]["location"] == "Pune, India"
            assert result["input"]["crop_type"] == "Rice"
            assert result["risk_level"] == "LOW"
            assert result["confidence"] == 95 # 0.95 * 100
            assert result["weather_analysis"]["overall_risk"] == "LOW"
            assert result["soil_analysis"]["suitability_rating"] == "good"
            assert result["crop_action_plan"]["overall_assessment"] == "Conditions are highly favorable for crop growth."
            assert "schedule" in result
            assert "timestamps" in result
            assert "metadata" in result
            
            # Ensure tools were called
            mock_weather_fetch.assert_called_once_with("Pune, India")
            mock_soil_get.assert_called_once_with("Pune, India", "Rice")


@pytest.mark.asyncio
async def test_run_pipeline_trigger_refinement(mock_gemini_response):
    # Test that if confidence is low, or risk is HIGH, the orchestrator triggers refinement.
    # In mock_gemini_response, let's modify the initial crop_action response to have confidence 0.3 (low).
    # The refinement loop should then trigger. We'll return a refined response.
    
    mock_weather_raw = {
        "temperature_avg_c": 35.0,
        "temperature_max_c": 42.0,
        "severe_weather_risk": "HIGH",
    }
    mock_soil_raw = {"soil_type": "Clay"}
    
    initial_crop_plan = dict(mock_gemini_response["crop_action"])
    initial_crop_plan["confidence"] = 0.3  # Triggers refinement because it's below the 0.6 threshold
    
    refined_crop_plan = dict(mock_gemini_response["crop_action"])
    refined_crop_plan["confidence"] = 0.8
    refined_crop_plan["contingency_plans"] = ["Water crops twice daily due to high risk"]

    gemini_calls = []

    async def mock_call_gemini_side_effect(prompt):
        gemini_calls.append(prompt)
        if "analyze this weather forecast" in prompt.lower():
            return json.dumps(mock_gemini_response["weather_analyst"])
        elif "analyze this soil profile data" in prompt.lower():
            return json.dumps(mock_gemini_response["soil_parameter"])
        elif "refine this action plan" in prompt.lower():
            return json.dumps(refined_crop_plan)
        elif "create an action plan" in prompt.lower():
            return json.dumps(initial_crop_plan)
        return "{}"

    with patch("backend.agents.weather_agent.fetch_weather", AsyncMock(return_value=mock_weather_raw)), \
         patch("backend.agents.soil_agent.get_soil_profile", return_value=mock_soil_raw), \
         patch("backend.agents.base_agent.BaseAgent.call_gemini", AsyncMock(side_effect=mock_call_gemini_side_effect)):
         
         result = await run_pipeline(
             location="Pune, India",
             crop_type="Rice",
             farming_goal="Water Conservation",
             notes=""
         )
         
         # The result should contain the refined plan
         assert result["confidence"] == 80
         assert result["metadata"]["refinement_iterations"] >= 1
         assert len(result["metadata"]["refinement_reasons"]) >= 1
         assert "low confidence" in result["metadata"]["refinement_reasons"][0]
