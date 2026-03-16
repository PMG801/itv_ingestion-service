from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from core.messaging import RabbitMQClient
from core.messaging.consumer import RabbitMQConsumer


class DummyIncomingMessage:
    def __init__(self, body: bytes) -> None:
        self.body = body
        self.ack = AsyncMock()
        self.reject = AsyncMock()


@pytest.fixture(autouse=True)
def reset_rabbitmq_singleton() -> None:
    RabbitMQClient._instance = None
    try:
        yield
    finally:
        RabbitMQClient._instance = None


@pytest.mark.asyncio
async def test_consumer_process_message_acknowledges_valid_json() -> None:
    consumer = RabbitMQConsumer()
    callback = AsyncMock()
    message = DummyIncomingMessage(
        json.dumps({"message_id": "m1", "source": "catalunya"}).encode("utf-8")
    )

    await consumer._process_message(message=message, callback=callback, auto_ack=False)

    callback.assert_awaited_once_with({"message_id": "m1", "source": "catalunya"})
    message.ack.assert_awaited_once()
    message.reject.assert_not_called()


@pytest.mark.asyncio
async def test_consumer_process_message_rejects_invalid_json() -> None:
    consumer = RabbitMQConsumer()
    callback = AsyncMock()
    message = DummyIncomingMessage(b"not-json")

    await consumer._process_message(message=message, callback=callback, auto_ack=False)

    callback.assert_not_called()
    message.ack.assert_not_called()
    message.reject.assert_awaited_once_with(requeue=False)


@pytest.mark.asyncio
async def test_rabbitmq_client_publish_serializes_and_uses_declared_exchange() -> None:
    client = RabbitMQClient()
    exchange = type("DummyExchange", (), {"publish": AsyncMock()})()
    client.connection = type("Conn", (), {"is_closed": False})()
    client.channel = type("Chan", (), {"is_closed": False})()
    client.exchanges = {"raw_data": exchange}

    await client.publish(
        message={"message_id": "m1", "count": 2},
        exchange_name="raw_data",
        routing_key="itv_stations",
    )

    exchange.publish.assert_awaited_once()


@pytest.mark.asyncio
async def test_rabbitmq_client_publish_requires_connection() -> None:
    client = RabbitMQClient()

    with pytest.raises(ValueError, match="not connected"):
        await client.publish(
            message={"message_id": "m1"},
            exchange_name="raw_data",
            routing_key="itv_stations",
        )