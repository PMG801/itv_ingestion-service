from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from apps.gateway.main import app as gateway_app
from apps.gateway.routers import ingest


class FakeRabbitMQ:
    def __init__(self, *, connected: bool = True) -> None:
        self.is_connected = connected
        self.publish = AsyncMock()


@pytest.fixture
async def gateway_client() -> AsyncClient:
    transport = ASGITransport(app=gateway_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.fixture
async def ingest_client() -> AsyncClient:
    test_app = FastAPI()
    test_app.include_router(ingest.router, prefix="/api/v1")
    transport = ASGITransport(app=test_app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        client.app = test_app
        yield client


@pytest.mark.asyncio
async def test_ingest_endpoint_queues_message_and_returns_tracking_id(
    ingest_client: AsyncClient,
) -> None:
    rabbitmq = FakeRabbitMQ()
    ingest_client.app.state.rabbitmq = rabbitmq

    response = await ingest_client.post(
        "/api/v1/ingest/catalunya",
        json={
            "payload": {"stations": [{"id": "BCN-001"}]},
            "format": "json",
        },
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "accepted"
    assert body["message"].startswith("Data from catalunya queued")
    assert body["message_id"]

    rabbitmq.publish.assert_awaited_once()
    publish_call = rabbitmq.publish.await_args
    assert publish_call.kwargs["exchange_name"] == "raw_data"
    assert publish_call.kwargs["routing_key"] == "itv_stations"
    assert publish_call.kwargs["message"]["source"] == "catalunya"


@pytest.mark.asyncio
async def test_ingest_endpoint_returns_503_when_rabbitmq_is_unavailable(
    ingest_client: AsyncClient,
) -> None:
    ingest_client.app.state.rabbitmq = FakeRabbitMQ(connected=False)

    response = await ingest_client.post(
        "/api/v1/ingest/valencia",
        json={"payload": {"estaciones": []}, "format": "json"},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Messaging service unavailable - not connected"


@pytest.mark.asyncio
async def test_list_sources_returns_supported_providers(ingest_client: AsyncClient) -> None:
    response = await ingest_client.get("/api/v1/sources")

    assert response.status_code == 200
    assert response.json()["sources"] == ["catalunya", "valencia", "galicia"]


@pytest.mark.asyncio
async def test_root_endpoint_returns_service_metadata(gateway_client: AsyncClient) -> None:
    response = await gateway_client.get("/")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "ITV Ingestion Gateway"
    assert body["status"] == "running"


@pytest.mark.asyncio
async def test_health_endpoint_reports_healthy_when_rabbitmq_is_connected(
    gateway_client: AsyncClient,
) -> None:
    gateway_app.state.rabbitmq = FakeRabbitMQ(connected=True)

    response = await gateway_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "service": "gateway",
        "version": "0.1.0",
        "rabbitmq_connected": True,
    }


@pytest.mark.asyncio
async def test_health_endpoint_reports_degraded_without_rabbitmq(
    gateway_client: AsyncClient,
) -> None:
    gateway_app.state._state.pop("rabbitmq", None)

    response = await gateway_client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert response.json()["rabbitmq_connected"] is False