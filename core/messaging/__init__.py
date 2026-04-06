from __future__ import annotations

"""
Messaging module - RabbitMQ async connection and publishing.

This module provides a singleton RabbitMQClient for managing async connections
to RabbitMQ using aio-pika, declaring topology (exchanges, queues, bindings),
and publishing persistent messages.
"""

import json
import logging
import socket
from typing import Any

import aio_pika
from aio_pika import (
    DeliveryMode,
    Message,
    ExchangeType,
)
from aio_pika.abc import AbstractChannel, AbstractExchange, AbstractQueue, AbstractRobustConnection

from core.config import settings

logger = logging.getLogger(__name__)


class RabbitMQClient:
    """
    Singleton client for managing RabbitMQ connections and operations.

    This client handles connection lifecycle, topology declaration (exchanges,
    queues, bindings), and message publishing with persistence and error handling.

    Attributes:
        connection: aio-pika robust connection to RabbitMQ.
        channel: aio-pika channel for operations.
        exchanges: Dictionary of declared exchanges.
        queues: Dictionary of declared queues.
    """

    _instance: RabbitMQClient | None = None
    _initialized: bool

    def __new__(cls) -> "RabbitMQClient":
        """Ensure only one instance exists (Singleton pattern)."""
        if cls._instance is None:
            instance = super().__new__(cls)
            instance._initialized = False
            cls._instance = instance
        return cls._instance

    def __init__(self) -> None:
        """Initialize RabbitMQClient (only once due to singleton)."""
        if self._initialized:
            return

        self.connection: AbstractRobustConnection | None = None
        self.channel: AbstractChannel | None = None
        self.exchanges: dict[str, AbstractExchange] = {}
        self.queues: dict[str, AbstractQueue] = {}
        self._initialized = True

    def _require_channel(self) -> AbstractChannel:
        if self.channel is None:
            raise RuntimeError("RabbitMQ channel is not initialized")
        return self.channel

    async def connect(self) -> None:
        """
        Establish connection to RabbitMQ and declare topology.

        Creates a robust connection (auto-reconnect), opens a channel, and
        declares all required exchanges, queues, and bindings idempotently.

        Topology declared:
            - Exchange: raw_data (topic, durable)
            - Exchange: normalized_data (topic, durable)
            - Exchange: dlx (topic, durable) - Dead Letter Exchange
            - Queue: raw_data.itv_stations (durable, with DLX)
            - Queue: normalized_data.itv_stations (durable, with DLX)
            - Queue: dlq.raw_data.itv_stations (Dead Letter Queue)
            - Queue: dlq.normalized_data.itv_stations (Dead Letter Queue)
            - Bindings with routing_key: itv_stations

        Raises:
            aio_pika.exceptions.AMQPException: If connection fails.
        """
        try:
            # Get container/hostname for connection traceability
            container_name = socket.gethostname()
            connection_name = f"{settings.APP_NAME}-{container_name}"

            logger.info(
                f"Connecting to RabbitMQ at {settings.RABBITMQ_HOST}:"
                f"{settings.RABBITMQ_PORT}/{settings.RABBITMQ_VHOST} "
                f"with connection_name: {connection_name}"
            )

            # Create robust connection (auto-reconnect on failure)
            # The connection_name parameter sets the client connection name in RabbitMQ
            self.connection = await aio_pika.connect_robust(
                host=settings.RABBITMQ_HOST,
                port=settings.RABBITMQ_PORT,
                login=settings.RABBITMQ_USER,
                password=settings.RABBITMQ_PASS,
                virtualhost=settings.RABBITMQ_VHOST,
                client_properties={
                    "connection_name": connection_name,
                },
                timeout=10,
                connection_name=connection_name,  # This sets the visible name in RabbitMQ management
            )

            # Open channel
            self.channel = await self.connection.channel()
            await self._require_channel().set_qos(prefetch_count=10)

            logger.info("Successfully connected to RabbitMQ")

            # Declare topology
            await self._declare_topology()

        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}", exc_info=True)
            raise

    async def _declare_topology(self) -> None:
        """
        Declare exchanges, queues, and bindings idempotently.

        This method is idempotent - it can be called multiple times without
        side effects. RabbitMQ will not recreate existing resources.
        """
        logger.info("Declaring RabbitMQ topology...")
        channel = self._require_channel()

        # Declare Dead Letter Exchange (DLX) first
        dlx_exchange = await channel.declare_exchange(
            name="dlx",
            type=ExchangeType.TOPIC,
            durable=True,
        )
        self.exchanges["dlx"] = dlx_exchange
        logger.debug("Declared Dead Letter Exchange (dlx)")

        # Declare main exchanges
        raw_data_exchange = await channel.declare_exchange(
            name="raw_data",
            type=ExchangeType.TOPIC,
            durable=True,
        )
        self.exchanges["raw_data"] = raw_data_exchange
        logger.debug("Declared exchange: raw_data (topic, durable)")

        normalized_data_exchange = await channel.declare_exchange(
            name="normalized_data",
            type=ExchangeType.TOPIC,
            durable=True,
        )
        self.exchanges["normalized_data"] = normalized_data_exchange
        logger.debug("Declared exchange: normalized_data (topic, durable)")

        rejected_data_exchange = await channel.declare_exchange(
            name="rejected_data",
            type=ExchangeType.TOPIC,
            durable=True,
        )
        self.exchanges["rejected_data"] = rejected_data_exchange
        logger.debug("Declared exchange: rejected_data (topic, durable)")

        # Declare Dead Letter Queues (DLQ) - no DLX for DLQs themselves
        dlq_raw = await channel.declare_queue(
            name="dlq.raw_data.itv_stations",
            durable=True,
        )
        self.queues["dlq.raw_data.itv_stations"] = dlq_raw
        logger.debug("Declared DLQ: dlq.raw_data.itv_stations")

        dlq_normalized = await channel.declare_queue(
            name="dlq.normalized_data.itv_stations",
            durable=True,
        )
        self.queues["dlq.normalized_data.itv_stations"] = dlq_normalized
        logger.debug("Declared DLQ: dlq.normalized_data.itv_stations")

        dlq_rejected = await channel.declare_queue(
            name="dlq.rejected_data.itv_stations",
            durable=True,
        )
        self.queues["dlq.rejected_data.itv_stations"] = dlq_rejected
        logger.debug("Declared DLQ: dlq.rejected_data.itv_stations")

        # Bind DLQs to DLX
        await dlq_raw.bind(
            exchange=dlx_exchange,
            routing_key="dlx.raw_data.itv_stations",
        )
        await dlq_normalized.bind(
            exchange=dlx_exchange,
            routing_key="dlx.normalized_data.itv_stations",
        )
        await dlq_rejected.bind(
            exchange=dlx_exchange,
            routing_key="dlx.rejected_data.itv_stations",
        )

        # Declare main queues with DLX configuration
        raw_queue = await channel.declare_queue(
            name="raw_data.itv_stations",
            durable=True,
            arguments={
                "x-dead-letter-exchange": "dlx",
                "x-dead-letter-routing-key": "dlx.raw_data.itv_stations",
            },
        )
        self.queues["raw_data.itv_stations"] = raw_queue
        logger.debug("Declared queue: raw_data.itv_stations (durable, with DLX)")

        normalized_queue = await channel.declare_queue(
            name="normalized_data.itv_stations",
            durable=True,
            arguments={
                "x-dead-letter-exchange": "dlx",
                "x-dead-letter-routing-key": "dlx.normalized_data.itv_stations",
            },
        )
        self.queues["normalized_data.itv_stations"] = normalized_queue
        logger.debug("Declared queue: normalized_data.itv_stations (durable, with DLX)")

        rejected_queue = await channel.declare_queue(
            name="rejected_data.itv_stations",
            durable=True,
            arguments={
                "x-dead-letter-exchange": "dlx",
                "x-dead-letter-routing-key": "dlx.rejected_data.itv_stations",
            },
        )
        self.queues["rejected_data.itv_stations"] = rejected_queue
        logger.debug("Declared queue: rejected_data.itv_stations (durable, with DLX)")

        # Bind queues to exchanges
        await raw_queue.bind(
            exchange=raw_data_exchange,
            routing_key="itv_stations",
        )
        logger.debug("Bound raw_data.itv_stations -> raw_data exchange (routing_key: itv_stations)")

        await normalized_queue.bind(
            exchange=normalized_data_exchange,
            routing_key="itv_stations",
        )
        logger.debug(
            "Bound normalized_data.itv_stations -> normalized_data exchange (routing_key: itv_stations)"
        )

        await rejected_queue.bind(
            exchange=rejected_data_exchange,
            routing_key="itv_stations",
        )
        logger.debug(
            "Bound rejected_data.itv_stations -> rejected_data exchange (routing_key: itv_stations)"
        )

        logger.info("RabbitMQ topology declared successfully")

    async def publish(
        self,
        message: dict[str, Any],
        exchange_name: str,
        routing_key: str,
    ) -> None:
        """
        Publish a message to RabbitMQ with persistence.

        Serializes the message to JSON and publishes it with DeliveryMode.PERSISTENT
        to ensure messages survive broker restarts.

        Args:
            message: Dictionary to serialize and publish.
            exchange_name: Name of the target exchange.
            routing_key: Routing key for message routing.

        Raises:
            ValueError: If exchange doesn't exist or channel not initialized.
            aio_pika.exceptions.AMQPException: If publish fails.
        """
        if self.channel is None or self.connection is None:
            raise ValueError("RabbitMQ client not connected. Call connect() first.")

        if exchange_name not in self.exchanges:
            raise ValueError(f"Exchange '{exchange_name}' not declared.")

        try:
            # Serialize message to JSON
            message_body = json.dumps(message, default=str).encode("utf-8")

            # Create persistent message
            aio_message = Message(
                body=message_body,
                delivery_mode=DeliveryMode.PERSISTENT,
                content_type="application/json",
            )

            # Publish to exchange
            exchange = self.exchanges[exchange_name]
            await exchange.publish(
                message=aio_message,
                routing_key=routing_key,
            )

            logger.debug(
                f"Published message to exchange='{exchange_name}', " f"routing_key='{routing_key}'"
            )

        except Exception as e:
            logger.error(
                f"Failed to publish message to {exchange_name}/{routing_key}: {e}",
                exc_info=True,
            )
            raise

    async def disconnect(self) -> None:
        """
        Close RabbitMQ connection gracefully.

        Closes the channel and connection. Should be called during
        application shutdown.
        """
        try:
            if self.channel and not self.channel.is_closed:
                await self.channel.close()
                logger.debug("Closed RabbitMQ channel")

            if self.connection and not self.connection.is_closed:
                await self.connection.close()
                logger.info("Disconnected from RabbitMQ")

        except Exception as e:
            logger.error(f"Error during RabbitMQ disconnect: {e}", exc_info=True)
        finally:
            self.channel = None
            self.connection = None
            self.exchanges.clear()
            self.queues.clear()

    @property
    def is_connected(self) -> bool:
        """Check if client is connected to RabbitMQ."""
        return (
            self.connection is not None
            and not self.connection.is_closed
            and self.channel is not None
            and not self.channel.is_closed
        )


# Export consumer for convenience
from core.messaging.consumer import RabbitMQConsumer  # noqa: E402

__all__ = ["RabbitMQClient", "RabbitMQConsumer"]
