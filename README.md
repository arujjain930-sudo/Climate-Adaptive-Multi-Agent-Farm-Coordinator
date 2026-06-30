# 🌾 Climate-Adaptive Multi-Agent Farm Coordinator 🌾

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100.0%2B-green.svg)](https://fastapi.tiangolo.com/)
[![Gemini 2.5 Flash](https://img.shields.io/badge/Gemini-2.5%20Flash-orange.svg)](https://deepmind.google/technologies/gemini/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An autonomous multi-agent agricultural intelligence network that processes live weather forecasts, geocoding coordinates, and regional soil profiles. Powered by **Google Gemini 2.5 Flash**, it delivers highly customized, dynamic crop protection strategies and week-by-week action calendars for smallholder farmers.

This project was built as a capstone submission for the Kaggle **"Agents for Good"** track, prioritizing data truthfulness, key rotation limits protection (free-tier safety), modular multi-agent orchestration, and a premium Glassmorphism UI.

---

## ⚡ Quick Start (Run Locally in 2 Minutes)

1. **Navigate to the project directory**:
   ```bash
   cd C:\Users\HP\Desktop\climate-farm-coordinator
   ```

2. **Create and activate a virtual environment**:
   ```bash
   python -m venv venv
   # On Windows:
   .\venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install the dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up your environment variables**:
   Create a `.env` file in the root directory based on `.env.example` and add your Google Gemini API keys:
   ```env
   GEMINI_API_KEY_1=your-first-key
   GEMINI_API_KEY_2=your-second-key
   ```

5. **Start the FastAPI server**:
   ```bash
   python -m backend.main
   ```

6. **Open your browser** and navigate to [http://127.0.0.1:8000](http://127.0.0.1:8000) to view the application!

---

## 📖 Table of Contents
- [Problem Statement](#-problem-statement)
- [Why Multi-Agent?](#-why-multi-agent)
- [Architecture & Data Flow](#-architecture--data-flow)
- [Key Features](#-key-features)
- [Tech Stack](#-tech-stack)
- [Environment Variables](#-environment-variables)
- [API Documentation](#-api-documentation)
- [CLI Testing Tool](#-cli-testing-tool)
- [Running Tests](#-running-tests)
- [Security Implementations](#-security-implementations)
- [Limitations & Future Enhancements](#-limitations--future-enhancements)
- [License](#-license)

---

## 🚨 Problem Statement

Smallholder farmers manage over 80% of the world's farms, yet they are the most vulnerable to climate change. With increasing weather unpredictability, traditional crop calendars are no longer reliable. Access to personalized agronomic advice is rare, and soil tests are often expensive or unavailable.

To build climate resilience, farmers need real-time, localized, and crop-specific strategies. **Climate-Adaptive Farm Coordinator** fills this gap by turning public weather forecasts and regional soil profiles into clear, weekly agricultural action schedules.

---

## 🤖 Why Multi-Agent?

Using a single, general LLM prompt to digest raw weather forecasts, soil datasets, crop requirements, and farm management goals often leads to reasoning dilution, formatting errors, and ungrounded advice ("hallucinations").

This coordinator breaks down the problem using a **modular, three-specialist agent network**:

1. **Weather Analyst Agent**: Specializes in parsing 7-day meteorological aggregates, identifying critical thresholds (e.g., frost points, extreme heat, flood risks) specific to the target crop.
2. **Soil Parameter Agent**: Focuses on matching the location to regional soil profiles (pH, nutrient levels, drainage) and evaluates crop suitability and required organic amendments.
3. **Crop Action Agent**: Synthesizes the analysis of the Weather and Soil agents into a unified, actionable 4-week calendar, resolving conflicting constraints (e.g., postponing fertilizer application if heavy rains are predicted).

### 🔄 The Refinement Loop
If the Crop Action Agent's output confidence is below the threshold (`0.6`) or if the severe weather risk is classified as **HIGH** or **EXTREME**, the orchestrator initiates a **refinement loop**. It sends the initial plan back to the Crop Action Agent with specific refinement instructions to build detailed risk-mitigation contingencies.

---

## 🏗️ Architecture & Data Flow

```
                       [ Farmer / Evaluator UI ]
                                   │
                    (POST /api/analyze with inputs)
                                   │
                                   ▼
                         [ FastAPI Backend ]
                                   │
                      (Validates & Sanitizes Input)
                                   │
                                   ▼
                       [ Agent Orchestrator ]
                                   │
          ┌────────────────────────┴────────────────────────┐
          │ (Concurrently via asyncio.gather)               │
          ▼                                                 ▼
 [ Weather Analyst Agent ]                         [ Soil Parameter Agent ]
    ├── Nominatim (Geocoding)                         └── Soil Profile Db
    ├── Open-Meteo (7-Day Weather API)                   (12 Curated Regions)
    └── Gemini 2.5 Flash                              └── Gemini 2.5 Flash
          │                                                 │
          │ (Weather Risk Summary)                          │ (Soil Health Summary)
          └────────────────────────┬────────────────────────┘
                                   │
                                   ▼
                        [ Crop Action Agent ]
                           ├── Gemini 2.5 Flash
                           └── (Synthesizes 4-Week Plan)
                                   │
                Is Confidence < 0.6 OR Risk HIGH/EXTREME?
                          ├── YES ──> [ Refinement Loop ] (Capped at 2)
                          └── NO
                                   │
                                   ▼
                  [ Output Formatter (JSON Response) ]
                                   │
                                   ▼
                      [ Polished UI Render / CLI ]
```

---

## 🎨 Key Features

- **Dual API Key Rotation**: Alternates dynamically between `GEMINI_API_KEY_1` and `GEMINI_API_KEY_2` across requests, doubling the free-tier quota limits (15 RPM / 1,500 RPD safety).
- **Verified & Disclaimer-Free Advice**: Configured prompt templates to enforce 100% true, authentic agronomic information. The models are prohibited from outputting speculative risk disclaimers (like "consult a local agronomist").
- **Dynamic Rule-Based Fallbacks**: If both keys fail or are throttled (429 errors), the backend automatically runs a custom local generator, calculating risk profiles and crop schedules mathematically from Open-Meteo and the regional soil database.
- **Parallel Agent Execution**: Concurrently runs Weather and Soil analyses, cutting LLM latency in half.
- **Modern responsive UI with 10 Premium Animations**: 
  - Onload landing header slide-downs, form slide-ups, and particle entries.
  - Interactive glassmorphic hover card lifts.
  - Sequential timeline fade reveals and flowing loading bar steps.
- **CLI Testing Tool**: Command-line interface to execute pipelines directly from the terminal.
- **Input Sanitization & CORS**: Built-in protection against XSS and SQL injection.

---

## 🛠️ Tech Stack

- **Backend Framework**: [FastAPI](https://fastapi.tiangolo.com/) (Python 3.10+)
- **WSGI/ASGI Server**: [Uvicorn](https://www.uvicorn.org/)
- **AI Model**: [Google Gemini 2.5 Flash](https://deepmind.google/technologies/gemini/) (via `google-generativeai` SDK)
- **APIs Used**: [Open-Meteo API](https://open-meteo.com/) (Weather), [OpenStreetMap Nominatim](https://nominatim.org/) (Geocoding)
- **Rate Limiting**: [SlowAPI](https://github.com/laurentS/slowapi) (Token bucket rate limiter)
- **Validation**: [Pydantic v2](https://docs.pydantic.dev/latest/)
- **Frontend**: Vanilla HTML5, CSS3 (variables, animations), and ES6 JavaScript.

---

## 🔌 API Documentation

### 1. `GET /api/health`
Check the health status of the application and configuration.
* **Response**:
  ```json
  {
    "status": "healthy",
    "model": "gemini-2.5-flash",
    "version": "1.0.0"
  }
  ```

### 2. `GET /api/sample`
Returns pre-packaged coordinates and crops to fill mock values on the front end.

### 3. `POST /api/analyze`
Submits farm data and executes the agent pipeline.

---

## 🛠️ CLI Testing Tool

You can test the agent orchestrator directly from the terminal without launching the web server:
```bash
python -m scripts.test_pipeline --location "Nairobi, Kenya" --crop "Maize" --goal "Maximize Yield"
```

---

## 🧪 Running Tests

The test suite covers input validation, geocoding fallbacks, agent failures, response structures, and CORS configuration.
To run the unit tests:
```bash
pytest -v
```

---

## 🔒 Security Implementations

1. **Environment-Driven Secrets**: The system accesses rotated API keys via env configuration. No secrets are stored in code or sent to the browser.
2. **Strict Regex Sanitization**: User inputs are stripped of dangerous structures (e.g., HTML/Script tags, SQL keywords, and special escape sequences).
3. **CORS Isolation**: Configured to restrict origin requests solely to configured local endpoints.
4. **FastAPI Security Headers**: Every HTTP response is served with security headers protecting against Clickjacking, MIME sniffing, and script execution.
5. **SlowAPI Protection**: Prevents denial of service and key quota exhaustion.

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
