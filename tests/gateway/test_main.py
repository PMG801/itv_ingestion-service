"""Tests for gateway main FastAPI application."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from apps.gateway.main import app, health_check, root


@pytest.fixture
def client() -> TestClient:
    """Create a test client for the FastAPI app."""
    return TestClient(app)


def test_root_endpoint_returns_service_info(client: TestClient) -> None:
    """Test that root endpoint returns service information."""
    response = client.get("/")
    
    assert response.status_code == 200
    assert response.json()["service"] == "ITV Ingestion Gateway"
    assert response.json()["version"] == "0.1.0"
    assert response.json()["status"] == "running"


@pytest.mark.asyncio
async def test_health_check_with_connected_rabbitmq() -> None:
    """Test health check when RabbitMQ is connected."""
    app.state.rabbitmq = MagicMock()
    app.state.rabbitmq.is_connected = True
    
    result = await health_check()
    
    assert result["status"] == "healthy"
    assert result["rabbitmq_connected"] is True
    assert result["service"] == "gateway"


@pytest.mark.asyncio
async def test_health_check_without_rabbitmq() -> None:
    """Test health check when RabbitMQ is not available."""
    # Remove rabbitmq from app state if it exists
    if hasattr(app.state, "rabbitmq"):
        delattr(app.state, "rabbitmq")
    
    result = await health_check()
    
    assert result["status"] == "degraded"
    assert result["rabbitmq_connected"] is False


@pytest.mark.asyncio
async def test_health_check_with_disconnected_rabbitmq() -> None:
    """Test health check when RabbitMQ is disconnected."""
    app.state.rabbitmq = MagicMock()
    app.state.rabbitmq.is_connected = False
    
    result = await health_check()
    
    assert result["status"] == "degraded"
    assert result["rabbitmq_connected"] is False


def test_app_includes_ingest_router(client: TestClient) -> None:
    """Test that ingest router is registered."""
    # The ingest router should handle /api/v1 routes
    assert any(
        "/api/v1" in str(route.path) for route in app.routes
    )


def test_app_has_cors_middleware() -> None:
    """Test that CORS middleware is configured."""
    # Check that middleware stack includes CORS
    cors_middleware_found = any(
        "CORSMiddleware" in str(middleware)
        for middleware in app.user_middleware
    )
    assert cors_middleware_found


def test_root_response_has_required_fields(client: TestClient) -> None:
    """Test that root response contains all required fields."""
    response = client.get("/")
    data = response.json()
    
    required_fields = ["service", "version", "status", "description"]
    assert all(field in data for field in required_fields)
