"""
RabbitMQ async consumer wrapper.

Provides a high-level interface for consuming messages from RabbitMQ queues
with automatic acknowledgment, error handling, and reconnection support.
"""

import logging
import json
from typing import Callable, Awaitable, Any

import aio_pika
from aio_pika.abc import AbstractChannel, AbstractIncomingMessage, AbstractRobustConnection

from core.config import settings

logger = logging.getLogger(__name__)


class RabbitMQConsumer:
    """
    Async consumer for RabbitMQ queues.
    
    Provides a high-level interface for consuming messages with automatic
    JSON deserialization, error handling, and message acknowledgment.
    
    Attributes:
        connection: Robust connection to RabbitMQ (auto-reconnect).
        channel: Channel for consuming messages.
    """
    
    def __init__(self):
        """Initialize RabbitMQ consumer."""
        self.connection: AbstractRobustConnection | None = None
        self.channel: AbstractChannel | None = None
    
    async def connect(self) -> None:
        """
        Establish connection to RabbitMQ.
        
        Creates a robust connection that automatically reconnects on failure.
        
        Raises:
            Exception: If connection fails.
        """
        try:
            logger.info(
                f"Connecting consumer to RabbitMQ at "
                f"{settings.RABBITMQ_HOST}:{settings.RABBITMQ_PORT}"
            )
            
            # Create robust connection (auto-reconnect on failure)
            self.connection = await aio_pika.connect_robust(
                url=settings.RABBITMQ_URL,
                timeout=10,
            )
            
            # Open channel
            self.channel = await self.connection.channel()
            
            # Set QoS (prefetch count) - process N messages at a time
            await self.channel.set_qos(prefetch_count=10)
            
            logger.info("Consumer connected to RabbitMQ successfully")
            
        except Exception as e:
            logger.error(f"Failed to connect consumer to RabbitMQ: {e}", exc_info=True)
            raise
    
    async def consume(
        self,
        queue_name: str,
        callback: Callable[[dict[str, Any]], Awaitable[None]],
        auto_ack: bool = False,
        arguments: dict[str, Any] | None = None,
    ) -> None:
        """
        Start consuming messages from a queue.
        
        Continuously consumes messages from the specified queue and invokes
        the callback function for each message. Messages are automatically
        acknowledged on success or rejected (sent to DLQ) on failure.
        
        Args:
            queue_name: Name of the queue to consume from.
            callback: Async function to process each message.
                Should accept a dict (deserialized JSON message).
            auto_ack: If True, messages are acknowledged immediately.
                If False (default), manual acknowledgment after callback.
            arguments: Optional queue arguments (e.g., DLX configuration).
                Must match the arguments used when the queue was created.
                
        Raises:
            Exception: If queue declaration or consumption fails.
            
        Example:
            >>> consumer = RabbitMQConsumer()
            >>> await consumer.connect()
            >>> 
            >>> async def process_message(data: dict):
            ...     print(f"Processing: {data}")
            >>> 
            >>> # With DLX configuration
            >>> dlx_args = {
            ...     "x-dead-letter-exchange": "dlx",
            ...     "x-dead-letter-routing-key": "my_queue.dlq"
            ... }
            >>> await consumer.consume("my_queue", process_message, arguments=dlx_args)
        """
        if self.channel is None:
            raise RuntimeError("Consumer not connected. Call connect() first.")
        channel = self.channel
        
        try:
            # Declare queue (idempotent - won't recreate if exists)
            # Must use same arguments as original queue declaration
            queue = await channel.declare_queue(
                queue_name,
                durable=True,
                arguments=arguments,
            )
            
            logger.info(f"Starting to consume from queue: {queue_name}")
            
            # Consume messages
            async with queue.iterator() as queue_iter:
                message: AbstractIncomingMessage
                async for message in queue_iter:
                    await self._process_message(
                        message=message,
                        callback=callback,
                        auto_ack=auto_ack,
                    )
                    
        except Exception as e:
            logger.error(f"Error consuming from queue {queue_name}: {e}", exc_info=True)
            raise
    
    async def _process_message(
        self,
        message: AbstractIncomingMessage,
        callback: Callable[[dict[str, Any]], Awaitable[None]],
        auto_ack: bool,
    ) -> None:
        """
        Process a single message.
        
        Args:
            message: Incoming RabbitMQ message.
            callback: Function to process the message.
            auto_ack: Whether to auto-acknowledge messages.
        """
        try:
            # Deserialize JSON payload
            payload = json.loads(message.body.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("RabbitMQ message payload must be a JSON object")
            
            logger.debug(
                f"Received message: {payload.get('message_id', 'unknown')} "
                f"from {payload.get('source', 'unknown')}"
            )
            
            # Process message
            await callback(payload)
            
            # Acknowledge message (if not auto-ack)
            if not auto_ack:
                await message.ack()
            
            logger.debug(f"Successfully processed message")
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode message JSON: {e}")
            # Reject message and send to DLQ (don't requeue)
            await message.reject(requeue=False)
            
        except Exception as e:
            logger.error(
                f"Error processing message: {e}",
                exc_info=True
            )
            # Reject message and send to DLQ (don't requeue)
            await message.reject(requeue=False)
    
    async def disconnect(self) -> None:
        """
        Close RabbitMQ connection gracefully.
        
        Should be called during application shutdown to ensure proper
        cleanup of resources.
        """
        try:
            if self.channel and not self.channel.is_closed:
                await self.channel.close()
                logger.debug("Consumer channel closed")
            
            if self.connection and not self.connection.is_closed:
                await self.connection.close()
                logger.info("Consumer disconnected from RabbitMQ")
                
        except Exception as e:
            logger.error(f"Error during consumer disconnect: {e}", exc_info=True)
        finally:
            self.channel = None
            self.connection = None
    
    @property
    def is_connected(self) -> bool:
        """
        Check if consumer is connected to RabbitMQ.
        
        Returns:
            True if connected, False otherwise.
        """
        return (
            self.connection is not None
            and not self.connection.is_closed
            and self.channel is not None
            and not self.channel.is_closed
        )
