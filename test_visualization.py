#!/usr/bin/env python3
"""
Test script to demonstrate the enhanced visualization endpoints with Google Drive integration
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

def test_timeline_visualization():
    """Test the timeline visualization endpoint"""
    print("\n=== Testing Timeline Visualization ===")
    
    # Test PNG format (will upload to Google Drive)
    print("\n1. Generating PNG timeline visualization...")
    response = requests.get(
        f"{BASE_URL}/visualize/timeline",
        params={"format": "png"},
        headers=HEADERS
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"✓ Success! Visualization uploaded to Google Drive")
        print(f"  Shareable Link: {result['shareable_link']}")
        print(f"  File ID: {result['file_id']}")
        print(f"  Filename: {result['filename']}")
    else:
        print(f"✗ Error: {response.status_code}")
        print(f"  Details: {response.text}")
    
    # Test with state filter
    print("\n2. Generating filtered timeline visualization...")
    response = requests.get(
        f"{BASE_URL}/visualize/timeline",
        params={
            "format": "png",
            "filter_states": "In Master,Agent Running"
        },
        headers=HEADERS
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"✓ Success! Filtered visualization uploaded")
        print(f"  Shareable Link: {result['shareable_link']}")
    else:
        print(f"✗ Error: {response.status_code}")
        print(f"  Details: {response.text}")

def test_stats_visualization():
    """Test the statistics visualization endpoint"""
    print("\n=== Testing Statistics Visualization ===")
    
    # Test JSON format (original behavior)
    print("\n1. Getting statistics in JSON format...")
    response = requests.get(
        f"{BASE_URL}/visualize/stats",
        params={"format": "json"},
        headers=HEADERS
    )
    
    if response.status_code == 200:
        stats = response.json()
        print(f"✓ Success! Got statistics for {stats['total_issues']} issues")
        print(f"  States tracked: {len(stats['states_tracked'])}")
        print(f"  Teams: {len(stats['team_distribution'])}")
    else:
        print(f"✗ Error: {response.status_code}")
        print(f"  Details: {response.text}")
    
    # Test PNG format (will upload to Google Drive)
    print("\n2. Generating PNG statistics dashboard...")
    response = requests.get(
        f"{BASE_URL}/visualize/stats",
        params={"format": "png"},
        headers=HEADERS
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"✓ Success! Statistics dashboard uploaded to Google Drive")
        print(f"  Shareable Link: {result['shareable_link']}")
        print(f"  File ID: {result['file_id']}")
        print(f"  Filename: {result['filename']}")
    else:
        print(f"✗ Error: {response.status_code}")
        print(f"  Details: {response.text}")

def main():
    """Run all tests"""
    print("Starting visualization tests...")
    print(f"Using API endpoint: {BASE_URL}")
    print(f"Using API key: {API_KEY[:10]}...")
    
    # Check if server is running
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code != 200:
            print("✗ Server is not responding. Please start the server first.")
            return
    except requests.ConnectionError:
        print("✗ Cannot connect to server. Please start the server with:")
        print("  python main.py")
        return
    
    print("✓ Server is running")
    
    # Run tests
    test_timeline_visualization()
    time.sleep(2)  # Small delay between tests
    test_stats_visualization()
    
    print("\n=== All tests completed ===")
    print("\nNote: Check your Google Drive for the uploaded visualizations!")
    print("The shareable links can be shared with anyone - they don't need")
    print("Google account access to view the images.")

if __name__ == "__main__":
    main()
