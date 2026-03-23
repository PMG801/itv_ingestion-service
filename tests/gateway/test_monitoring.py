"""Tests for monitoring router endpoints."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from fastapi import FastAPI

from apps.gateway.routers import monitoring


@pytest.fixture
async def monitoring_client() -> AsyncClient:
    """Create async HTTP client for monitoring router."""
    test_app = FastAPI()
    test_app.include_router(monitoring.router)
    transport = ASGITransport(app=test_app)
    
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        client.app = test_app
        yield client


@pytest.mark.asyncio
async def test_get_ingest_status_endpoint_returns_status_for_valid_message_id(
    monitoring_client: AsyncClient,
) -> None:
    """Test that monitoring endpoint returns ingestion status."""
    with patch(
        "apps.gateway.routers.monitoring.get_ingest_status",
        new_callable=AsyncMock,
    ) as mock_get_status:
        mock_get_status.return_value = {
            "message_id": "test-uuid-123",
            "status": "success",
            "source_system": "catalunya",
            "timing": {
                "gateway_latency_ms": 50,
                "normalizer_duration_ms": 1200,
                "persister_duration_ms": 300,
                "total_duration_ms": 1550,
            },
            "stations": {"successful": 100, "failed": 5},
            "rejection_summary": {
                "total_stations": 105,
                "rejected_count": 5,
                "rejection_reasons": {"invalid_coordinates": 3, "duplicate": 2},
            },
            "injection_type": "api",
            "processed_at": "2026-03-20T12:00:00+00:00",
        }

        response = await monitoring_client.get("/api/v1/monitoring/ingest/test-uuid-123")

        assert response.status_code == 200
        body = response.json()
        assert body["message_id"] == "test-uuid-123"
        assert body["status"] == "success"
        assert body["source_system"] == "catalunya"
        assert body["timing"]["total_duration_ms"] == 1550
        assert body["stations"]["successful"] == 100


@pytest.mark.asyncio
async def test_get_ingest_status_endpoint_returns_404_for_missing_message_id(
    monitoring_client: AsyncClient,
) -> None:
    """Test that monitoring endpoint returns 404 for non-existent message ID."""
    with patch(
        "apps.gateway.routers.monitoring.get_ingest_status",
        new_callable=AsyncMock,
    ) as mock_get_status:
        mock_get_status.return_value = None

        response = await monitoring_client.get("/api/v1/monitoring/ingest/nonexistent-id")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_metrics_endpoint_returns_aggregated_metrics(
    monitoring_client: AsyncClient,
) -> None:
    """Test that metrics endpoint returns aggregated system metrics."""
    with patch(
        "apps.gateway.routers.monitoring.get_metrics_aggregation",
        new_callable=AsyncMock,
    ) as mock_get_metrics:
        mock_get_metrics.return_value = {
            "success_rate_percent": 95.5,
            "total_messages": 200,
            "successful": 191,
            "failed": 9,
            "period_hours": 24,
            "avg_latency_ms": 1500.25,
            "p95_latency_ms": 2100.0,
            "p99_latency_ms": 2800.5,
            "error_rate_by_source": {
                "catalunya": 2.5,
                "valencia": 4.0,
                "galicia": 3.2,
            },
            "per_source_stats": {
                "catalunya": {"total": 100, "successful": 98, "failed": 2, "rate": 98.0},
                "valencia": {"total": 50, "successful": 48, "failed": 2, "rate": 96.0},
                "galicia": {"total": 50, "successful": 45, "failed": 5, "rate": 90.0},
            },
            "top_rejection_reasons": [
                {"reason": "invalid_coordinates", "count": 5, "percentage": 55.5},
                {"reason": "duplicate", "count": 4, "percentage": 44.5},
            ],
            "timestamp": "2026-03-21T12:00:00+00:00",
        }

        response = await monitoring_client.get("/api/v1/monitoring/metrics?period_hours=24")

        assert response.status_code == 200
        body = response.json()
        assert body["success_rate_percent"] == 95.5
        assert body["total_messages"] == 200
        assert body["period_hours"] == 24
        assert body["avg_latency_ms"] == 1500.25
        assert body["p95_latency_ms"] == 2100.0
        assert "per_source_stats" in body
        assert "top_rejection_reasons" in body


@pytest.mark.asyncio
async def test_get_metrics_endpoint_returns_empty_metrics_when_no_data(
    monitoring_client: AsyncClient,
) -> None:
    """Test metrics endpoint returns empty metrics when no data available."""
    with patch(
        "apps.gateway.routers.monitoring.get_metrics_aggregation",
        new_callable=AsyncMock,
    ) as mock_get_metrics:
        mock_get_metrics.return_value = {
            "success_rate_percent": 0.0,
            "total_messages": 0,
            "period_hours": 24,
            "avg_latency_ms": 0,
            "p95_latency_ms": 0,
            "p99_latency_ms": 0,
            "error_rate_by_source": {},
            "per_source_stats": {},
        }

        response = await monitoring_client.get("/api/v1/monitoring/metrics")

        assert response.status_code == 200
        assert response.json()["total_messages"] == 0


@pytest.mark.asyncio
async def test_get_metrics_endpoint_validates_period_hours_bounds(
    monitoring_client: AsyncClient,
) -> None:
    """Test that metrics endpoint validates period_hours query parameter bounds."""
    # Test with invalid period_hours (too low)
    response = await monitoring_client.get("/api/v1/monitoring/metrics?period_hours=0")
    assert response.status_code == 422  # Validation error

    # Test with invalid period_hours (too high)
    response = await monitoring_client.get("/api/v1/monitoring/metrics?period_hours=10000")
    assert response.status_code == 422  # Validation error
