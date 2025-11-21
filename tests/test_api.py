"""
Integration tests for API endpoints.
"""

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.mark.integration
def test_root_endpoint(client):
    """Test the root endpoint returns expected response."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "version" in data
    assert data["version"] == "0.1.0"


@pytest.mark.integration
def test_health_check(client):
    """Test the health check endpoint."""
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


@pytest.mark.integration
def test_readiness_check(client):
    """Test the readiness check endpoint."""
    response = client.get("/readyz")

    # Should be either 200 (ready) or 503 (not ready)
    # In tests, orchestrator may fail to init if GOOGLE_API_KEY not set
    assert response.status_code in [200, 503]

    data = response.json()
    if response.status_code == 200:
        assert data["status"] == "ready"
        assert "components" in data
    else:
        assert "detail" in data


@pytest.mark.integration
def test_chat_endpoint(client):
    """Test the chat endpoint with a basic message."""
    request_data = {
        "message": "Show me contemporary art exhibitions",
        "user_id": "test_user_001",
    }

    response = client.post("/chat", json=request_data)
    assert response.status_code == 200

    data = response.json()
    assert "response" in data
    assert "correlation_id" in data
    assert len(data["correlation_id"]) > 0
    # Response will either be from orchestrator or fallback message
    assert len(data["response"]) > 0


@pytest.mark.integration
def test_chat_endpoint_default_user(client):
    """Test chat endpoint uses default user_id when not provided."""
    request_data = {
        "message": "Find sculpture exhibitions",
    }

    response = client.post("/chat", json=request_data)
    assert response.status_code == 200

    data = response.json()
    assert "response" in data
    assert "correlation_id" in data


@pytest.mark.integration
def test_chat_endpoint_empty_message(client):
    """Test chat endpoint with empty message."""
    request_data = {
        "message": "",
        "user_id": "test_user_002",
    }

    response = client.post("/chat", json=request_data)
    # Should still work, just with empty echo
    assert response.status_code == 200


@pytest.mark.integration
def test_chat_endpoint_missing_message(client):
    """Test chat endpoint with missing message field."""
    request_data = {
        "user_id": "test_user_003",
    }

    response = client.post("/chat", json=request_data)
    # Should fail validation
    assert response.status_code == 422  # Unprocessable Entity
