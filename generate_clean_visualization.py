#!/usr/bin/env python3
"""
Generate a clean visualization to test the improvements
"""
import requests
import json
import time
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
BASE_URL = "http://localhost:8000"
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    print("ERROR: API_KEY environment variable is required")
    print("Please set it in your .env file")
    exit(1)
HEADERS = {"X-API-Key": API_KEY}

print("Generating improved timeline visualization...")
print("=" * 60)

# Generate PNG timeline visualization
response = requests.get(
    f"{BASE_URL}/visualize/timeline",
    params={"format": "png"},
    headers=HEADERS
)

if response.status_code == 200:
    result = response.json()
    print("✓ Success! Clean visualization generated and uploaded")
    print(f"\nShareable Link: {result['shareable_link']}")
    print(f"File ID: {result['file_id']}")
    print(f"Filename: {result['filename']}")
    print("\nImprovements made:")
    print("- Added vertical jitter to prevent overlapping points")
    print("- Different marker shapes for each state:")
    print("  • Circle (o) = Agent Running")
    print("  • Square (■) = Agent Change Needs Review") 
    print("  • Triangle (▲) = In Master")
    print("- Better color palette with distinct colors")
    print("- Enhanced grid and axis labels")
    print("- Issue labels with background for better readability")
    print("- Added 3 demo issues to show timeline connections clearly")
    print("\nOpen the shareable link to see the improved visualization!")
else:
    print(f"✗ Error: {response.status_code}")
    print(f"Details: {response.text}")
    print("\nMake sure the server is running:")
    print("  python main.py")
