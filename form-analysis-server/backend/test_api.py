"""
Test script for the Form Analysis API endpoints.

Tests basic functionality without requiring a database connection.
"""

import asyncio
import sys
from typing import Dict, Any

from fastapi.testclient import TestClient
from app.main import app

def test_endpoints():
    """Test all available endpoints."""
    client = TestClient(app)
    
    results = []
    
    # Test root endpoint
    print("Testing root endpoint...")
    try:
        response = client.get("/")
        results.append({
            "endpoint": "/",
            "status": response.status_code,
            "success": response.status_code == 200,
            "data": response.json() if response.status_code == 200 else None
        })
        print(f" Root endpoint: {response.status_code}")
    except Exception as e:
        results.append({
            "endpoint": "/",
            "status": None,
            "success": False,
            "error": str(e)
        })
        print(f" Root endpoint failed: {e}")
    
    # Test basic health check
    print("\nTesting basic health check...")
    try:
        response = client.get("/healthz")
        results.append({
            "endpoint": "/healthz",
            "status": response.status_code,
            "success": response.status_code == 200,
            "data": response.json() if response.status_code == 200 else None
        })
        print(f" Basic health check: {response.status_code}")
    except Exception as e:
        results.append({
            "endpoint": "/healthz",
            "status": None,
            "success": False,
            "error": str(e)
        })
        print(f" Basic health check failed: {e}")
    
    # Test liveness check
    print("\nTesting liveness check...")
    try:
        response = client.get("/healthz/live")
        results.append({
            "endpoint": "/healthz/live",
            "status": response.status_code,
            "success": response.status_code == 200,
            "data": response.json() if response.status_code == 200 else None
        })
        print(f" Liveness check: {response.status_code}")
    except Exception as e:
        results.append({
            "endpoint": "/healthz/live",
            "status": None,
            "success": False,
            "error": str(e)
        })
        print(f" Liveness check failed: {e}")
    
    # Test docs endpoint
    print("\nTesting API docs...")
    try:
        response = client.get("/docs")
        results.append({
            "endpoint": "/docs",
            "status": response.status_code,
            "success": response.status_code == 200,
        })
        print(f" API docs: {response.status_code}")
    except Exception as e:
        results.append({
            "endpoint": "/docs",
            "status": None,
            "success": False,
            "error": str(e)
        })
        print(f" API docs failed: {e}")
    
    # Summary
    successful = sum(1 for r in results if r.get("success", False))
    total = len(results)
    
    print(f"\n Test Summary:")
    print(f"    Successful: {successful}/{total}")
    print(f"    Failed: {total - successful}/{total}")
    
    if successful == total:
        print("\n All tests passed! The API is working correctly.")
        return True
    else:
        print("\n  Some tests failed. Check the details above.")
        return False

if __name__ == "__main__":
    print("Testing Form Analysis API endpoints...")
    print("=" * 50)
    
    success = test_endpoints()
    
    if not success:
        sys.exit(1)