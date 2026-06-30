#!/usr/bin/env python3
"""
CLI tool to test the Climate-Adaptive Farm Coordinator pipeline directly.
Does not require running the FastAPI server.

Usage:
    python -m scripts.test_pipeline --location "Pune, India" --crop "Rice" --goal "Water Conservation"
"""

import argparse
import asyncio
import json
import os
import sys
from dotenv import load_dotenv

# Load env variables from .env if present
load_dotenv()

# Add project root to sys.path so we can import backend packages
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.orchestrator import run_pipeline
from backend.utils.validators import validate_analyze_input


async def main():
    parser = argparse.ArgumentParser(
        description="Run the Climate-Adaptive Farm Coordinator multi-agent pipeline from the CLI."
    )
    parser.add_argument(
        "--location",
        required=True,
        help="Target location name (e.g., 'Punjab, India')",
    )
    parser.add_argument(
        "--crop",
        required=True,
        help="Target crop name (e.g., 'wheat', 'rice')",
    )
    parser.add_argument(
        "--goal",
        default="General Guidance",
        help="Farmer's goal (default: 'General Guidance')",
    )
    parser.add_argument(
        "--notes",
        default="",
        help="Optional notes (e.g., 'irrigated')",
    )

    args = parser.parse_args()

    # Verify GEMINI_API_KEY is configured
    if not os.environ.get("GEMINI_API_KEY"):
        print("❌ Error: GEMINI_API_KEY environment variable is not set.", file=sys.stderr)
        print("Please set it in your environment or create a .env file.", file=sys.stderr)
        sys.exit(1)

    print("🌾 Starting Climate-Adaptive Multi-Agent Farm Coordinator 🌾")
    print(f"📍 Location: {args.location}")
    print(f"🌱 Crop:     {args.crop}")
    print(f"🎯 Goal:     {args.goal}")
    if args.notes:
        print(f"📝 Notes:    {args.notes}")
    print("-" * 60)

    # Validate inputs
    try:
        clean_input = validate_analyze_input({
            "location": args.location,
            "crop_type": args.crop,
            "farming_goal": args.goal,
            "notes": args.notes
        })
    except ValueError as ve:
        print(f"❌ Input validation failed: {ve}", file=sys.stderr)
        sys.exit(1)

    print("🤖 Launching agent pipeline...")
    print("⏳ Weather Analyst & Soil Parameter agents running concurrently...")
    
    try:
        result = await run_pipeline(
            location=clean_input["location"],
            crop_type=clean_input["crop_type"],
            farming_goal=clean_input["farming_goal"],
            notes=clean_input["notes"]
        )
    except Exception as exc:
        print(f"❌ Pipeline execution failed: {exc}", file=sys.stderr)
        sys.exit(1)

    print("✅ Pipeline execution completed successfully!\n")
    
    # Print Results
    print("=" * 60)
    print("  SUMMARY RECOMMENDATION")
    print("=" * 60)
    print(f"Headline:    {result.get('summary')}")
    print(f"Risk Level:  {result.get('risk_level')}")
    print(f"Urgency:     {result.get('urgency')}")
    print(f"Confidence:  {result.get('confidence')}%")
    print(f"Primary Rec: {result.get('key_recommendation')}")
    print()

    print("=" * 60)
    print("  WEATHER ANALYSIS AGENT")
    print("=" * 60)
    weather = result.get("weather_analysis", {})
    print(f"Overall Weather Risk: {weather.get('overall_risk')}")
    print(f"Temperature:          {weather.get('temperature_assessment')}")
    print(f"Precipitation:        {weather.get('precipitation_assessment')}")
    print(f"Wind:                 {weather.get('wind_assessment')}")
    print("Key Risks:")
    for risk in weather.get("key_risks", []):
        print(f"  - {risk}")
    print("Precautions:")
    for prec in weather.get("precautions", []):
        print(f"  - {prec}")
    print()

    print("=" * 60)
    print("  SOIL PARAMETER AGENT")
    print("=" * 60)
    soil = result.get("soil_analysis", {})
    print(f"Soil Suitability: {soil.get('suitability_rating')}")
    print(f"pH Assessment:    {soil.get('ph_assessment')}")
    print(f"Nutrient:         {soil.get('nutrient_assessment')}")
    print(f"Drainage:         {soil.get('drainage_assessment')}")
    print("Key Issues:")
    for issue in soil.get("key_issues", []):
        print(f"  - {issue}")
    print("Recommended Amendments:")
    for amend in soil.get("amendments", []):
        print(f"  - {amend}")
    print()

    print("=" * 60)
    print("  CROP ACTION PLAN AGENT")
    print("=" * 60)
    crop = result.get("crop_action_plan", {})
    print(f"Irrigation Plan: {crop.get('irrigation_plan')}")
    print(f"Fertilizer Plan: {crop.get('fertilizer_plan')}")
    print("Pest/Disease Watch:")
    for watch in crop.get("pest_disease_watch", []):
        print(f"  - {watch}")
    print("Climate Adaptation Tips:")
    for tip in crop.get("climate_adaptation_tips", []):
        print(f"  - {tip}")
    if "contingency_plans" in crop:
        print("Refinement Contingency Plans:")
        for cp in crop.get("contingency_plans", []):
            print(f"  - {cp}")
    print()

    print("=" * 60)
    print("  WEEKLY ACTION SCHEDULE")
    print("=" * 60)
    schedule = result.get("schedule", {})
    for week_num, week_data in schedule.items():
        print(f"📅 {week_num.replace('_', ' ').title()}: {week_data.get('focus', 'Monitoring')}")
        for task in week_data.get("tasks", []):
            print(f"  [ ] {task}")
    print()

    print("=" * 60)
    print("  PIPELINE PERFORMANCE METADATA")
    print("=" * 60)
    metadata = result.get("metadata", {})
    print(f"Execution Time:        {metadata.get('total_time_seconds')} seconds")
    print(f"Refinement Iterations: {metadata.get('refinement_iterations')}")
    if metadata.get("refinement_reasons"):
        print(f"Refinement Reasons:    {', '.join(metadata.get('refinement_reasons'))}")
    print()


if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
