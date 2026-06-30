import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi.testclient import TestClient

# Mock settings before importing app
with patch("backend.config.get_settings") as mock_settings_fn:
    mock_settings = MagicMock()
    mock_settings.gemini_api_key = "mock-key"
    mock_settings.gemini_model = "gemini-2.0-flash-lite"
    mock_settings.gemini_temperature = 0.2
    mock_settings.max_refinement_iterations = 2
    mock_settings.confidence_threshold = 0.6
    mock_settings.rate_limit = "5/minute"
    mock_settings.origins_list = ["http://localhost:3000", "http://localhost:8000"]
    mock_settings.max_location_length = 100
    mock_settings.max_crop_type_length = 60
    mock_settings.max_goal_length = 200
    mock_settings.max_notes_length = 500
    mock_settings_fn.return_value = mock_settings

    from backend.main import app

@pytest.fixture
def client():
    """FastAPI TestClient fixture."""
    return TestClient(app)

@pytest.fixture
def mock_gemini_response():
    """Default mocked Gemini API response helper."""
    return {
        "weather_analyst": {
            "overall_risk": "LOW",
            "temperature_assessment": "Mild temperatures, perfect for wheat.",
            "precipitation_assessment": "No heavy rain forecast.",
            "wind_assessment": "Moderate breeze, no risk.",
            "key_risks": [],
            "precautions": ["Monitor soil moisture"],
            "favorable_conditions": ["Sunny days"],
            "confidence": 0.9
        },
        "soil_parameter": {
            "suitability_rating": "good",
            "ph_assessment": "pH 6.5 is suitable.",
            "nutrient_assessment": "Moderate nitrogen, high phosphorus.",
            "drainage_assessment": "Well-drained soil.",
            "key_issues": [],
            "amendments": ["Apply balanced NPK fertilizer"],
            "soil_strengths": ["Excellent structure"],
            "confidence": 0.8
        },
        "crop_action": {
            "overall_assessment": "Conditions are highly favorable for crop growth.",
            "risk_level": "LOW",
            "confidence": 0.95,
            "immediate_actions": ["Prepare tools for sowing"],
            "weekly_schedule": {
                "week_1": {
                    "focus": "Sowing",
                    "tasks": ["Sow seeds at recommended depth"]
                },
                "week_2": {
                    "focus": "Irrigation",
                    "tasks": ["Water lightly in the morning"]
                },
                "week_3": {
                    "focus": "Fertilizing",
                    "tasks": ["Apply initial nitrogen dose"]
                },
                "week_4": {
                    "focus": "Monitoring",
                    "tasks": ["Inspect leaves for pests"]
                }
            },
            "irrigation_plan": "Water twice a week early morning.",
            "fertilizer_plan": "Apply urea at week 3.",
            "pest_disease_watch": ["Aphids", "Mildew"],
            "climate_adaptation_tips": ["Use organic mulch to retain moisture."]
        }
    }


@pytest.fixture(autouse=True)
def clear_orchestrator_cache():
    """Autouse fixture to clear the backend cache before each test."""
    from backend.orchestrator import _pipeline_cache
    _pipeline_cache.clear()

