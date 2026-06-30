import pytest
import json
from unittest.mock import patch, AsyncMock

def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "model" in data

def test_sample_endpoint(client):
    response = client.get("/api/sample")
    assert response.status_code == 200
    data = response.json()
    assert "samples" in data
    assert len(data["samples"]) > 0
    assert data["samples"][0]["location"] is not None

def test_architecture_endpoint(client):
    response = client.get("/api/architecture")
    assert response.status_code == 200
    data = response.json()
    assert "pipeline_name" in data
    assert "agents" in data
    assert "execution_flow" in data

def test_analyze_endpoint_validation_errors(client):
    # Missing location (Pydantic validation error -> 422)
    response = client.post("/api/analyze", json={"crop_type": "Rice"})
    assert response.status_code == 422

    # Too long location (Pydantic validation error -> 422)
    response = client.post("/api/analyze", json={"location": "A" * 200, "crop_type": "Rice"})
    assert response.status_code == 422

    # Custom validator error: only invalid characters (ValueError -> 400)
    response = client.post("/api/analyze", json={"location": "$$$", "crop_type": "Rice"})
    assert response.status_code == 400
    data = response.json()
    assert "error" in data


@pytest.mark.asyncio
async def test_analyze_endpoint_success(client, mock_gemini_response):
    # Mock orchestrator run_pipeline so we don't do actual run
    mock_pipeline_output = {
        "status": "success",
        "input": {
            "location": "Pune, India",
            "crop_type": "Rice",
            "farming_goal": "Water Conservation",
            "notes": ""
        },
        "summary": "Conditions are highly favorable for crop growth.",
        "risk_level": "LOW",
        "urgency": "Normal",
        "confidence": 95,
        "key_recommendation": "Prepare tools for sowing",
        "weather_analysis": mock_gemini_response["weather_analyst"],
        "soil_analysis": mock_gemini_response["soil_parameter"],
        "crop_action_plan": mock_gemini_response["crop_action"],
        "schedule": mock_gemini_response["crop_action"]["weekly_schedule"],
        "timestamps": {"pipeline_start": "2026-06-30T12:00:00Z", "pipeline_end": "2026-06-30T12:00:02Z"},
        "metadata": {"total_time_seconds": 2.0}
    }

    with patch("backend.main.run_pipeline", AsyncMock(return_value=mock_pipeline_output)):
        response = client.post("/api/analyze", json={
            "location": "Pune, India",
            "crop_type": "Rice",
            "farming_goal": "Water Conservation",
            "notes": ""
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["risk_level"] == "LOW"
        assert data["confidence"] == 95
        assert "weather_analysis" in data
        assert "soil_analysis" in data
        assert "crop_action_plan" in data
        assert "schedule" in data
