"""
Integration tests for Dockerized service.

Tests health checks, chat endpoint, and preference updates against
a running Docker container.
"""

import os
import time

import pytest
import requests

# Docker service URL
BASE_URL = os.getenv("TEST_SERVICE_URL", "http://localhost:8000")

# Skip these tests if SERVICE_URL not set (not in Docker test mode)
pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DOCKER_TESTS") != "true",
    reason="Docker integration tests disabled (set RUN_DOCKER_TESTS=true to enable)",
)


@pytest.fixture(scope="module")
def wait_for_service():
    """Wait for the Docker service to be ready."""
    max_retries = 30
    retry_interval = 2

    for i in range(max_retries):
        try:
            response = requests.get(f"{BASE_URL}/healthz", timeout=5)
            if response.status_code == 200:
                print(f"\n✓ Service ready after {i * retry_interval}s")
                return True
        except requests.exceptions.RequestException:
            if i < max_retries - 1:
                time.sleep(retry_interval)
            continue

    pytest.fail(f"Service did not become ready after {max_retries * retry_interval}s")


def test_health_check(wait_for_service):
    """Test liveness health check endpoint."""
    response = requests.get(f"{BASE_URL}/healthz", timeout=10)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "service" in data
    assert "version" in data


def test_readiness_check(wait_for_service):
    """Test readiness health check endpoint."""
    response = requests.get(f"{BASE_URL}/readyz", timeout=10)

    # Could be 200 (ready) or 503 (not ready if orchestrator failed to initialize)
    assert response.status_code in [200, 503]

    if response.status_code == 200:
        data = response.json()
        assert data["status"] == "ready"
        assert "components" in data
        assert data["components"]["orchestrator"] == "initialized"


def test_chat_endpoint_basic(wait_for_service):
    """Test basic chat endpoint functionality."""
    payload = {
        "message": "What art exhibitions are available?",
        "user_id": "test-user-docker-1",
    }

    response = requests.post(f"{BASE_URL}/chat", json=payload, timeout=30)

    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert "correlation_id" in data
    assert len(data["response"]) > 0
    assert len(data["correlation_id"]) > 0


def test_chat_endpoint_preference_update(wait_for_service):
    """Test preference update through chat endpoint."""
    user_id = "test-user-docker-2"

    # Update preferences
    payload = {"message": "I love contemporary art and sculpture", "user_id": user_id}

    response = requests.post(f"{BASE_URL}/chat", json=payload, timeout=30)

    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    # Response should acknowledge the preference
    assert any(
        word in data["response"].lower()
        for word in ["preference", "noted", "updated", "remember"]
    )


def test_chat_endpoint_multi_turn(wait_for_service):
    """Test multi-turn conversation."""
    user_id = "test-user-docker-3"

    # First turn: Set preference
    payload1 = {"message": "I like photography", "user_id": user_id}
    response1 = requests.post(f"{BASE_URL}/chat", json=payload1, timeout=30)
    assert response1.status_code == 200

    # Second turn: Request recommendations
    payload2 = {"message": "Show me some art events", "user_id": user_id}
    response2 = requests.post(f"{BASE_URL}/chat", json=payload2, timeout=30)
    assert response2.status_code == 200

    data2 = response2.json()
    assert "response" in data2


def test_chat_endpoint_error_handling(wait_for_service):
    """Test error handling for invalid requests."""
    # Missing message field
    payload = {"user_id": "test-user-docker-4"}

    response = requests.post(f"{BASE_URL}/chat", json=payload, timeout=10)

    # Should return 422 Unprocessable Entity for validation error
    assert response.status_code == 422


def test_root_endpoint(wait_for_service):
    """Test root endpoint."""
    response = requests.get(f"{BASE_URL}/", timeout=10)

    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "version" in data
