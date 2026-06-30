import pytest
from backend.utils.validators import validate_analyze_input, validate_location, validate_crop_type, validate_optional_text

def test_valid_inputs_pass():
    data = {
        "location": "Pune, Maharashtra, India",
        "crop_type": "Rice",
        "farming_goal": "Water Conservation",
        "notes": "Using drip irrigation system."
    }
    result = validate_analyze_input(data)
    assert result["location"] == "Pune, Maharashtra, India"
    assert result["crop_type"] == "Rice"
    assert result["farming_goal"] == "Water Conservation"
    assert result["notes"] == "Using drip irrigation system."

def test_missing_location_raises_error():
    data = {
        "location": "",
        "crop_type": "Rice"
    }
    with pytest.raises(ValueError, match="Location is required and cannot be empty"):
        validate_analyze_input(data)

def test_missing_crop_type_raises_error():
    data = {
        "location": "Pune, India",
        "crop_type": "  "
    }
    with pytest.raises(ValueError, match="Crop type is required and cannot be empty"):
        validate_analyze_input(data)

def test_location_too_long_raises_error():
    data = {
        "location": "A" * 105,
        "crop_type": "Rice"
    }
    with pytest.raises(ValueError, match="Location must be at most"):
        validate_analyze_input(data)

def test_crop_too_long_raises_error():
    data = {
        "location": "Pune, India",
        "crop_type": "B" * 65
    }
    with pytest.raises(ValueError, match="Crop type must be at most"):
        validate_analyze_input(data)

def test_sanitizes_xss_attempts():
    data = {
        "location": "Pune <script>alert(1)</script>, India",
        "crop_type": "Rice",
        "farming_goal": "Prevent <img src=x onerror=alert(1)> bugs",
        "notes": "Clean <iframe>this</iframe>"
    }
    result = validate_analyze_input(data)
    assert "<script>" not in result["location"]
    assert "</script>" not in result["location"]
    assert "<img" not in result["farming_goal"]
    assert "<iframe>" not in result["notes"]

def test_sanitizes_sql_injection():
    data = {
        "location": "Pune; DROP TABLE Users; --",
        "crop_type": "Rice",
        "farming_goal": "Normal Goal",
        "notes": "normal note"
    }
    result = validate_analyze_input(data)
    # The semi-colon is allowed in _SAFE_TEXT_RE but NOT in _SAFE_LOCATION_RE.
    # _SAFE_LOCATION_RE allows only alphanumeric and a few punctuation marks, NOT semi-colon.
    # Therefore, the semi-colon and DROP table characters will be cleaned based on the regex.
    # Let's verify:
    assert "DROP TABLE" in result["location"] # Wait, is DROP TABLE in location allowed? 
    # Yes, characters "D", "R", "O", "P", etc. are allowed by the regex.
    # But characters like ";" and "--" are cleaned or stripped.
    # Let's test that the cleaned version is safe.
    assert ";" not in result["location"]
