"""
Normalizer Worker - Transforms raw data to normalized format.

Consumes from: raw_data.itv_stations
Publishes to: normalized_data.itv_stations

This worker implements the core transformation logic using the Strategy Pattern.
It consumes raw messages from different sources (Catalunya, Valencia, Galicia),
applies the appropriate transformation strategy, and publishes normalized data.
"""

import asyncio
import logging
import sys
from typing import Dict, Any

from core.config import settings
from core.messaging import RabbitMQClient
from core.messaging.consumer import RabbitMQConsumer
from apps.normalizer.factory import TransformerFactory

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class NormalizerWorker:
    """
    Main normalizer worker that processes raw messages.
    
    This worker:
    1. Consumes raw messages from raw_data.itv_stations queue
    2. Selects appropriate transformer based on source_system
    3. Transforms raw data to NormalizedStation format
    4. Publishes normalized data to normalized_data.itv_stations queue
    
    Attributes:
        consumer: RabbitMQ consumer for reading messages.
        publisher: RabbitMQ client for publishing messages.
        factory: Transformer factory for creating source-specific transformers.
    """
    
    def __init__(self):
        """Initialize the normalizer worker."""
        self.consumer = RabbitMQConsumer()
        self.publisher = RabbitMQClient()
        self.factory = TransformerFactory()
        self.messages_processed = 0
        self.messages_failed = 0
    
    async def start(self) -> None:
        """
        Start the worker.
        
        Connects to RabbitMQ and starts consuming messages from the
        raw_data.itv_stations queue.
        """
        logger.info("=" * 60)
        logger.info(f"Starting {settings.APP_NAME} - Normalizer Worker")
        logger.info("=" * 60)
        logger.info(f"Log level: {settings.LOG_LEVEL}")
        logger.info(f"RabbitMQ: {settings.RABBITMQ_HOST}:{settings.RABBITMQ_PORT}")
        logger.info(f"Input queue: raw_data.itv_stations")
        logger.info(f"Output exchange: normalized_data")
        logger.info(f"Supported sources: {', '.join(self.factory.supported_sources())}")
        logger.info("=" * 60)
        
        try:
            # Connect consumer and publisher
            await self.consumer.connect()
            await self.publisher.connect()
            
            logger.info("✅ Connected to RabbitMQ - Ready to process messages")
            
            # DLX configuration - must match queue creation arguments
            dlx_args = {
                "x-dead-letter-exchange": "dlx",
                "x-dead-letter-routing-key": "dlx.raw_data.itv_stations",
            }
            
            # Start consuming messages
            await self.consumer.consume(
                queue_name="raw_data.itv_stations",
                callback=self.process_message,
                arguments=dlx_args,
            )
            
        except KeyboardInterrupt:
            logger.info("Received shutdown signal (Ctrl+C)")
        except Exception as e:
            logger.error(f"Fatal error in normalizer worker: {e}", exc_info=True)
            raise
    
    async def process_message(self, message: Dict[str, Any]) -> None:
        """
        Process a single raw message.
        
        Extracts the source system, selects the appropriate transformer,
        transforms the raw data, and publishes normalized stations.
        
        Args:
            message: RawIngestionMessage from gateway containing:
                - message_id: Unique identifier for tracing
                - source: Source system (catalunya, valencia, galicia)
                - payload: Raw data in source-specific format
                - format: Data format (json, xml, csv)
                - ingested_at: Ingestion timestamp
                
        Raises:
            Exception: If transformation fails critically (will send to DLQ).
        """
        message_id = message.get("message_id", "unknown")
        source = message.get("source", "unknown")
        payload = message.get("payload")
        data_format = message.get("format", "unknown")
        
        logger.info(
            f"📥 Processing message {message_id} | "
            f"source={source} | format={data_format}"
        )
        
        try:
            # Validate message structure
            if not source or not payload:
                raise ValueError(
                    f"Invalid message structure: missing source or payload"
                )
            
            # Get appropriate transformer for this source
            transformer = self.factory.create(source)
            
            logger.debug(
                f"Using {transformer.__class__.__name__} for source={source}"
            )
            
            # Transform raw data to normalized format
            normalized_stations = transformer.transform(payload)
            
            if not normalized_stations:
                logger.warning(
                    f"⚠️  No stations extracted from message {message_id}"
                )
                self.messages_processed += 1
                return
            
            logger.info(
                f"✅ Transformed {len(normalized_stations)} stations from {source}"
            )
            
            # Publish each normalized station to the next queue
            published_count = 0
            for station in normalized_stations:
                try:
                    await self.publisher.publish(
                        message=station.model_dump(mode="json"),
                        exchange_name="normalized_data",
                        routing_key="itv_stations",
                    )
                    published_count += 1
                except Exception as e:
                    logger.error(
                        f"Failed to publish station {station.station_id}: {e}"
                    )
                    # Continue with other stations
                    continue
            
            logger.info(
                f"📤 Published {published_count}/{len(normalized_stations)} "
                f"stations to normalized_data exchange"
            )
            
            self.messages_processed += 1
            
            # Log progress every 10 messages
            if self.messages_processed % 10 == 0:
                logger.info(
                    f"📊 Progress: {self.messages_processed} processed, "
                    f"{self.messages_failed} failed"
                )
            
        except ValueError as e:
            # Validation or transformation error - log and fail
            logger.error(
                f"❌ Validation error for message {message_id}: {e}"
            )
            self.messages_failed += 1
            raise  # Re-raise to send to DLQ
            
        except Exception as e:
            # Unexpected error - log and fail
            logger.error(
                f"❌ Error processing message {message_id}: {e}",
                exc_info=True
            )
            self.messages_failed += 1
            raise  # Re-raise to send to DLQ
    
    async def shutdown(self) -> None:
        """
        Graceful shutdown of the worker.
        
        Closes RabbitMQ connections and logs final statistics.
        """
        logger.info("=" * 60)
        logger.info("Shutting down Normalizer Worker...")
        logger.info(f"Final statistics:")
        logger.info(f"  - Messages processed: {self.messages_processed}")
        logger.info(f"  - Messages failed: {self.messages_failed}")
        logger.info("=" * 60)
        
        try:
            await self.consumer.disconnect()
            await self.publisher.disconnect()
            logger.info("✅ Shutdown complete")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}", exc_info=True)


async def main():
    """Main entry point for the normalizer worker."""
    worker = NormalizerWorker()
    
    try:
        await worker.start()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    except Exception as e:
        logger.error(f"Worker failed with error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        await worker.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker stopped by user")
        sys.exit(0)
