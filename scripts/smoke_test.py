#!/usr/bin/env python3
"""
Smoke tests for deployed BCN Art Compass service.

Tests health endpoints and basic chat functionality on Cloud Run.
"""

import argparse
import json
import sys
import time
from typing import Optional

import requests


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = '\033[0;32m'
    RED = '\033[0;31m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'  # No Color


def print_status(message: str, status: str) -> None:
    """Print a status message with color."""
    if status == "pass":
        print(f"{Colors.GREEN}✓{Colors.NC} {message}")
    elif status == "fail":
        print(f"{Colors.RED}✗{Colors.NC} {message}")
    elif status == "info":
        print(f"{Colors.BLUE}ℹ{Colors.NC} {message}")
    elif status == "warn":
        print(f"{Colors.YELLOW}⚠{Colors.NC} {message}")


def test_health_endpoint(base_url: str, timeout: int = 10) -> bool:
    """
    Test /healthz endpoint.
    
    Args:
        base_url: Service base URL
        timeout: Request timeout in seconds
        
    Returns:
        bool: True if test passes
    """
    print_status("Testing /healthz endpoint...", "info")
    
    try:
        response = requests.get(f"{base_url}/healthz", timeout=timeout)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "healthy":
                print_status(f"Health check passed: {data}", "pass")
                return True
            else:
                print_status(f"Unexpected response: {data}", "fail")
                return False
        else:
            print_status(f"Health check failed: HTTP {response.status_code}", "fail")
            return False
            
    except requests.exceptions.Timeout:
        print_status(f"Health check timed out after {timeout}s", "fail")
        return False
    except requests.exceptions.RequestException as e:
        print_status(f"Health check error: {e}", "fail")
        return False


def test_readiness_endpoint(base_url: str, timeout: int = 10) -> bool:
    """
    Test /readyz endpoint.
    
    Args:
        base_url: Service base URL
        timeout: Request timeout in seconds
        
    Returns:
        bool: True if test passes
    """
    print_status("Testing /readyz endpoint...", "info")
    
    try:
        response = requests.get(f"{base_url}/readyz", timeout=timeout)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "ready":
                print_status(f"Readiness check passed: {data}", "pass")
                return True
            else:
                print_status(f"Service not ready: {data}", "warn")
                return False
        elif response.status_code == 503:
            data = response.json()
            print_status(f"Service not ready: {data}", "warn")
            return False
        else:
            print_status(f"Readiness check failed: HTTP {response.status_code}", "fail")
            return False
            
    except requests.exceptions.Timeout:
        print_status(f"Readiness check timed out after {timeout}s", "fail")
        return False
    except requests.exceptions.RequestException as e:
        print_status(f"Readiness check error: {e}", "fail")
        return False


def test_chat_endpoint(
    base_url: str,
    user_id: str = "smoke_test",
    timeout: int = 30,
) -> bool:
    """
    Test /chat endpoint with a simple query.
    
    Args:
        base_url: Service base URL
        user_id: User ID for testing
        timeout: Request timeout in seconds
        
    Returns:
        bool: True if test passes
    """
    print_status("Testing /chat endpoint...", "info")
    
    payload = {
        "message": "What art exhibitions are happening in Barcelona?",
        "user_id": user_id,
    }
    
    try:
        response = requests.post(
            f"{base_url}/chat",
            json=payload,
            timeout=timeout,
        )
        
        if response.status_code == 200:
            data = response.json()
            if "response" in data:
                response_text = data["response"]
                print_status(f"Chat response received ({len(response_text)} chars)", "pass")
                print(f"  Response preview: {response_text[:100]}...")
                return True
            else:
                print_status(f"Unexpected response format: {data}", "fail")
                return False
        else:
            print_status(f"Chat request failed: HTTP {response.status_code}", "fail")
            try:
                error_data = response.json()
                print(f"  Error: {error_data}")
            except:
                print(f"  Response: {response.text[:200]}")
            return False
            
    except requests.exceptions.Timeout:
        print_status(f"Chat request timed out after {timeout}s", "fail")
        return False
    except requests.exceptions.RequestException as e:
        print_status(f"Chat request error: {e}", "fail")
        return False


def wait_for_readiness(
    base_url: str,
    max_wait: int = 60,
    interval: int = 5,
) -> bool:
    """
    Wait for service to become ready.
    
    Args:
        base_url: Service base URL
        max_wait: Maximum wait time in seconds
        interval: Check interval in seconds
        
    Returns:
        bool: True if service becomes ready
    """
    print_status(f"Waiting for service to be ready (max {max_wait}s)...", "info")
    
    elapsed = 0
    while elapsed < max_wait:
        try:
            response = requests.get(f"{base_url}/readyz", timeout=5)
            if response.status_code == 200:
                print_status("Service is ready", "pass")
                return True
        except:
            pass
        
        time.sleep(interval)
        elapsed += interval
        print_status(f"  Still waiting... ({elapsed}/{max_wait}s)", "info")
    
    print_status("Service did not become ready in time", "fail")
    return False


def run_smoke_tests(
    service_url: str,
    skip_chat: bool = False,
    wait_ready: bool = True,
) -> bool:
    """
    Run all smoke tests.
    
    Args:
        service_url: Cloud Run service URL
        skip_chat: Skip chat endpoint test
        wait_ready: Wait for service to be ready before testing
        
    Returns:
        bool: True if all tests pass
    """
    print(f"{Colors.BLUE}{'='*60}{Colors.NC}")
    print(f"{Colors.BLUE}BCN Art Compass - Smoke Tests{Colors.NC}")
    print(f"{Colors.BLUE}{'='*60}{Colors.NC}")
    print(f"Service URL: {service_url}")
    print()
    
    results = []
    
    # Test health endpoint
    results.append(("Health", test_health_endpoint(service_url)))
    print()
    
    # Wait for readiness if requested
    if wait_ready:
        ready = wait_for_readiness(service_url)
        results.append(("Readiness Wait", ready))
        print()
        
        if not ready:
            print_status("Service not ready, skipping further tests", "warn")
            return False
    
    # Test readiness endpoint
    results.append(("Readiness", test_readiness_endpoint(service_url)))
    print()
    
    # Test chat endpoint
    if not skip_chat:
        results.append(("Chat", test_chat_endpoint(service_url)))
        print()
    
    # Summary
    print(f"{Colors.BLUE}{'='*60}{Colors.NC}")
    print(f"{Colors.BLUE}Test Summary{Colors.NC}")
    print(f"{Colors.BLUE}{'='*60}{Colors.NC}")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "pass" if result else "fail"
        print_status(f"{name}: {'PASS' if result else 'FAIL'}", status)
    
    print()
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print_status("All tests passed!", "pass")
        return True
    else:
        print_status(f"{total - passed} test(s) failed", "fail")
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run smoke tests against deployed BCN Art Compass service"
    )
    parser.add_argument(
        "service_url",
        help="Cloud Run service URL (e.g., https://bcn-art-compass-abc123-uc.a.run.app)",
    )
    parser.add_argument(
        "--skip-chat",
        action="store_true",
        help="Skip chat endpoint test",
    )
    parser.add_argument(
        "--no-wait",
        action="store_true",
        help="Don't wait for service to be ready",
    )
    
    args = parser.parse_args()
    
    # Remove trailing slash from URL
    service_url = args.service_url.rstrip("/")
    
    # Run tests
    success = run_smoke_tests(
        service_url,
        skip_chat=args.skip_chat,
        wait_ready=not args.no_wait,
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
