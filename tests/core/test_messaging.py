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


@pytest.mark.asyncio
async def test_rabbitmq_client_publish_requires_declared_exchange() -> None:
    client = RabbitMQClient()
    client.connection = type("Conn", (), {"is_closed": False})()
    client.channel = type("Chan", (), {"is_closed": False})()
    client.exchanges = {}

    with pytest.raises(ValueError, match="not declared"):
        await client.publish(
            message={"message_id": "m1"},
            exchange_name="nonexistent",
            routing_key="itv_stations",
        )


def test_rabbitmq_client_singleton_pattern() -> None:
    """Test that RabbitMQClient follows singleton pattern."""
    client1 = RabbitMQClient()
    client2 = RabbitMQClient()
    
    assert client1 is client2


def test_rabbitmq_client_is_connected_when_connection_none() -> None:
    """Test that is_connected returns False when connection is None."""
    # Create new instance after reset
    client = RabbitMQClient()
    # Ensure connection is None
    client.connection = None
    
    assert not client.is_connected


def test_rabbitmq_client_is_connected_when_connection_exists() -> None:
    """Test that is_connected returns True when connection and channel exist."""
    client = RabbitMQClient()
    client.connection = type("Conn", (), {"is_closed": False})()
    client.channel = type("Chan", (), {"is_closed": False})()
    
    assert client.is_connected


@pytest.mark.asyncio
async def test_consumer_process_message_auto_ack() -> None:
    """Test that auto_ack=True skips manual acknowledgment."""
    consumer = RabbitMQConsumer()
    callback = AsyncMock()
    message = DummyIncomingMessage(
        json.dumps({"message_id": "m1"}).encode("utf-8")
    )

    await consumer._process_message(message=message, callback=callback, auto_ack=True)

    callback.assert_awaited_once()
    # auto_ack=True means manual ack is skipped
    message.ack.assert_not_called()


@pytest.mark.asyncio
async def test_consumer_process_message_callback_exception_rejects() -> None:
    """Test that callback exceptions cause message rejection."""
    consumer = RabbitMQConsumer()
    callback = AsyncMock(side_effect=ValueError("Processing error"))
    message = DummyIncomingMessage(
        json.dumps({"message_id": "m1"}).encode("utf-8")
    )

    await consumer._process_message(message=message, callback=callback, auto_ack=False)

    callback.assert_awaited_once()
    message.ack.assert_not_called()
    message.reject.assert_awaited_once_with(requeue=False)


@pytest.mark.asyncio
async def test_rabbitmq_client_disconnect_clears_state() -> None:
    """Test that disconnect clears client state."""
    client = RabbitMQClient()
    client.connection = type("Conn", (), {
        "is_closed": False,
        "close": AsyncMock()
    })()
    client.channel = type("Chan", (), {
        "is_closed": False,
        "close": AsyncMock()
    })()
    client.exchanges = {"test": "exchange"}
    client.queues = {"test": "queue"}

    await client.disconnect()

    assert client.connection is None
    assert client.channel is None
    assert len(client.exchanges) == 0
    assert len(client.queues) == 0


@pytest.mark.asyncio
async def test_consumer_init() -> None:
    """Test that consumer initializes correctly."""
    consumer = RabbitMQConsumer()
    assert consumer.connection is None
    assert consumer.channel is None


@pytest.mark.asyncio
async def test_consumer_consume_raises_without_connect() -> None:
    """Test that consume raises RuntimeError if not connected."""
    consumer = RabbitMQConsumer()
    
    async def dummy_callback(data: dict) -> None:
        pass
    
    with pytest.raises(RuntimeError, match="not connected"):
        await consumer.consume("test_queue", dummy_callback)


@pytest.mark.asyncio
async def test_rabbitmq_client_require_channel() -> None:
    """Test that _require_channel raises when channel is None."""
    client = RabbitMQClient()
    
    with pytest.raises(RuntimeError, match="not initialized"):
        client._require_channel()


@pytest.mark.asyncio
async def test_rabbitmq_client_is_connected_false_cases() -> None:
    """Test various false conditions for is_connected."""
    client = RabbitMQClient()
    
    # No connection
    assert not client.is_connected
    
    # Only connection, no channel
    client.connection = type("Conn", (), {"is_closed": False})()
    assert not client.is_connected
    
    # Closed connection
    client.connection = type("Conn", (), {"is_closed": True})()
    client.channel = type("Chan", (), {"is_closed": False})()
    assert not client.is_connected
    
    # Closed channel
    client.connection = type("Conn", (), {"is_closed": False})()
    client.channel = type("Chan", (), {"is_closed": True})()
    assert not client.is_connected