# Project: Climate Farm Coordinator

## Architecture
The Climate Farm Coordinator is a multi-agent system composed of:
- **FastAPI Backend**: Serves API endpoints, applies security headers, rate limits requests, and manages static files.
- **Orchestrator**: Manages the execution flow of multiple agents. Starts Soil and Weather agents in parallel, parses their results, triggers Crop Action Agent, and runs a refinement loop if needed.
- **Weather Analyst Agent**: Fetches weather forecasts and analyzes weather risks using Gemini.
- **Soil Parameter Agent**: Fetches soil profiles from a local database and analyzes soil health.
- **Crop Action Agent**: Synthesizes soil/weather analyses and generates week-by-week action plans.
- **Frontend SPA**: A single-page dashboard featuring controls, dynamic badges, meters, and CSS animations.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Setup & Server Config | Set up `.env` with Gemini API key, Gitignore it, and verify backend configuration settings. | None | IN_PROGRESS (Conv: 6a0cfca5-f859-4a4f-80c5-d4d5aa5f905a) |
| 2 | UI Controls & Badging | Fix sample data loading in `frontend/app.js` and implement dynamic risk/confidence updates on screen. | None | PLANNED |
| 3 | Dynamic Fallback System | Implement a mock-plan dynamic fallback generator when Gemini API/quota fails. | None | PLANNED |
| 4 | CSS Animations | Add premium CSS transitions, hover states, status rings, and loading bars to UI. | M2 | PLANNED |
| 5 | Test Suite Verification | Correct mock prompt parsing logic in `tests/test_orchestration.py` and run units. | None | PLANNED |
| 6 | Integration & Verification | Run the completed test track (E2E) and perform adversarial hardening (Tier 5). | M1, M2, M3, M4, M5 | PLANNED |

## Interface Contracts
### `backend.orchestrator.run_pipeline`
- Signature: `async def run_pipeline(location: str, crop_type: str, farming_goal: str | None, notes: str | None) -> dict`
- Input: Parameters for localized agricultural strategy
- Output: Structured pipeline result containing `weather_analysis`, `soil_analysis`, `crop_action_plan`, confidence score, risk level, and execution metadata.

### `backend.agents.base_agent.BaseAgent.call_gemini`
- Signature: `async def call_gemini(self, prompt: str) -> str`
- Input: Text prompt
- Output: JSON string from Gemini 2.5 Flash

## Code Layout
- `.env` - Environment variables (ignored)
- `.gitignore` - Git ignore configurations
- `backend/`
  - `config.py` - Configuration settings with Pydantic
  - `main.py` - FastAPI app initialization, routes, static mount
  - `orchestrator.py` - Pipeline execution flow & cache
  - `agents/`
    - `base_agent.py` - Base class with Gemini calling logic
    - `weather_agent.py` - Weather analyst agent
    - `soil_agent.py` - Soil parameter agent
    - `crop_agent.py` - Crop action agent
  - `tools/`
    - `weather_api.py` - Nominatim and Open-Meteo interface
    - `soil_profiles.py` - Soil profile DB and lookup logic
  - `prompts/`
    - `templates.py` - Prompt string definitions for Gemini
  - `utils/`
    - `security.py` - CORS, security headers, rate limiting
    - `validators.py` - Sanitization and input regex validation
- `frontend/`
  - `index.html` - Dashboard HTML structure
  - `styles.css` - Dashboard styles & animations
  - `app.js` - SPA JavaScript controller
- `tests/`
  - `conftest.py` - Pytest fixtures and mocks
  - `test_orchestration.py` - Pipeline tests
  - `test_fallback.py` - Fallback behavior tests
  - `test_response.py` - API response tests
  - `test_validation.py` - Input validation tests
