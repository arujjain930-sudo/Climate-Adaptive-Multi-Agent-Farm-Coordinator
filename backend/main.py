"""
FastAPI application — entry point for the Climate-Adaptive Farm Coordinator.

Endpoints:
  POST /api/analyze       — run the full multi-agent pipeline
  GET  /api/health        — liveness check
  GET  /api/sample        — return sample input data for quick demos
  GET  /api/architecture  — describe the agent pipeline

Middleware stack (applied bottom-up):
  1. CORS                  — restrict to configured origins
  2. Security headers      — X-Content-Type-Options, X-Frame-Options, CSP …
  3. Rate limiting (SlowAPI)— 5 req/min per IP

Static files:
  The frontend is served from ../frontend/ so the entire app can run
  from a single uvicorn process.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from backend.config import get_settings
from backend.orchestrator import run_pipeline
from backend.utils.security import (
    add_security_headers,
    get_limiter,
    safe_error_response,
    sanitize_for_log,
)
from backend.utils.validators import validate_analyze_input

# ── Logging ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("farm_coordinator.main")

# ── App Initialisation ──────────────────────────────────────────────────
settings = get_settings()
limiter = get_limiter()

app = FastAPI(
    title="Climate-Adaptive Farm Coordinator",
    description="Multi-agent system for climate-aware farming recommendations",
    version="1.0.0",
    # Disable the auto-generated docs in production if desired;
    # leaving them on for the Kaggle demo.
    docs_url="/docs",
    redoc_url="/redoc",
)

# Attach the limiter's state to the app (SlowAPI requirement)
app.state.limiter = limiter

# ── Middleware (order matters: last added = first executed) ───────────────

# 1. CORS — only allow configured origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# 2. Security headers — injected on every response
app.middleware("http")(add_security_headers)

# 3. Rate-limit exceeded handler
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ── Request Models ───────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    """Validated request body for the /api/analyze endpoint."""
    location: str = Field(..., min_length=1, max_length=100, examples=["Punjab, India"])
    crop_type: str = Field(..., min_length=1, max_length=60, examples=["wheat"])
    farming_goal: str | None = Field(default=None, max_length=200, examples=["maximize yield"])
    notes: str | None = Field(default=None, max_length=500, examples=["Using drip irrigation"])


# ── Endpoints ────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health_check() -> dict[str, str]:
    """
    Simple liveness probe.

    Returns 200 with status "healthy" if the server is running and the
    Gemini API key is configured.
    """
    return {
        "status": "healthy",
        "model": settings.gemini_model,
        "version": "1.0.0",
    }


@app.get("/api/sample")
async def sample_input() -> dict[str, Any]:
    """
    Return pre-filled sample input data so the frontend can offer a
    "Try a demo" button without requiring the user to type anything.
    """
    return {
        "samples": [
            {
                "name": "Wheat in Punjab",
                "location": "Punjab, India",
                "crop_type": "wheat",
                "farming_goal": "maximize yield",
                "notes": "Irrigated farm, post-monsoon season",
            },
            {
                "name": "Rice in Kerala",
                "location": "Kerala, India",
                "crop_type": "rice",
                "farming_goal": "sustainable farming",
                "notes": "Small-holder farm with traditional practices",
            },
            {
                "name": "Maize in Kenya",
                "location": "Nairobi, Kenya",
                "crop_type": "maize",
                "farming_goal": "maximize yield",
                "notes": "Rain-fed agriculture, no irrigation available",
            },
            {
                "name": "Corn in Iowa",
                "location": "Iowa, USA",
                "crop_type": "corn",
                "farming_goal": "maximize yield while reducing input costs",
                "notes": "Large commercial farm with center-pivot irrigation",
            },
            {
                "name": "Cotton in Maharashtra",
                "location": "Maharashtra, India",
                "crop_type": "cotton",
                "farming_goal": "reduce water usage",
                "notes": "Dryland farming, erratic monsoon expected",
            },
        ],
    }


@app.get("/api/architecture")
async def architecture_info() -> dict[str, Any]:
    """
    Describe the agent pipeline so the frontend can render an
    architecture diagram or explanation card.
    """
    return {
        "pipeline_name": "Climate-Adaptive Multi-Agent Farm Coordinator",
        "model": settings.gemini_model,
        "agents": [
            {
                "name": "WeatherAnalystAgent",
                "role": "Fetches 7-day weather forecast via Open-Meteo API and interprets climate risks for the target crop using Gemini.",
                "tools": ["Open-Meteo API (weather)", "Nominatim (geocoding)"],
                "output": "Structured weather risk summary with confidence score",
            },
            {
                "name": "SoilParameterAgent",
                "role": "Looks up region/crop-specific soil profiles and interprets soil health and suitability using Gemini.",
                "tools": ["Rule-based soil profile database"],
                "output": "Structured soil health summary with amendment recommendations",
            },
            {
                "name": "CropActionAgent",
                "role": "Synthesises weather and soil analyses into a practical 4-week farming action plan with irrigation, fertilizer, and pest management recommendations.",
                "tools": [],
                "output": "Week-by-week action plan with risk mitigation strategies",
            },
        ],
        "execution_flow": [
            "1. WeatherAnalystAgent and SoilParameterAgent run IN PARALLEL (asyncio.gather)",
            "2. Their outputs are merged and passed to CropActionAgent",
            "3. If CropActionAgent confidence < 0.6 or risk is HIGH/EXTREME, a refinement loop runs (max 2 iterations)",
            "4. Final combined result is returned with all intermediate data and timestamps",
        ],
        "security": [
            "Rate limiting: 5 requests/minute per IP",
            "Input validation and sanitisation on all fields",
            "CORS restricted to localhost origins",
            "Security headers on every response",
            "API key stored in environment variable only",
            "Stack traces never exposed to client",
        ],
    }


@app.post("/api/analyze")
@limiter.limit(settings.rate_limit)
async def analyze(request: Request, body: AnalyzeRequest) -> JSONResponse:
    """
    Run the full multi-agent analysis pipeline.

    Accepts location, crop_type, and optional farming_goal / notes.
    Returns the complete pipeline output including weather analysis,
    soil analysis, crop action plan, and metadata.
    """
    # ── Validate & sanitise ──────────────────────────────────────────
    try:
        clean = validate_analyze_input(body.model_dump())
    except ValueError as ve:
        return safe_error_response(400, str(ve))

    logger.info(
        "Analyze request: location=%s crop=%s goal=%s",
        sanitize_for_log(clean["location"]),
        sanitize_for_log(clean["crop_type"]),
        sanitize_for_log(clean["farming_goal"]),
    )

    # ── Run pipeline ─────────────────────────────────────────────────
    try:
        result = await run_pipeline(
            location=clean["location"],
            crop_type=clean["crop_type"],
            farming_goal=clean["farming_goal"],
            notes=clean["notes"],
        )
        return JSONResponse(content=result)
    except Exception as exc:
        # Log the real error; return a safe message to the client.
        return safe_error_response(
            500,
            "The analysis pipeline encountered an error. Please try again.",
            detail=exc,
        )


# ── Static File Serving ─────────────────────────────────────────────────
# Mount the frontend build directory so the entire app can be served
# from a single process.  This must come AFTER the API routes so that
# /api/* paths are matched first.

_frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
if _frontend_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True), name="frontend")
    logger.info("Serving frontend static files from %s", _frontend_dir)
else:
    logger.warning(
        "Frontend directory not found at %s — static file serving disabled.",
        _frontend_dir,
    )


# ── Dev Server ───────────────────────────────────────────────────────────
# Allow running directly with `python -m backend.main` during development.

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )
