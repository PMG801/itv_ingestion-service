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
from typing import Any, Literal, cast
from datetime import datetime, timezone

from core.config import settings
from core.messaging import RabbitMQClient
from core.messaging.consumer import RabbitMQConsumer
from apps.normalizer.factory import TransformerFactory
from apps.normalizer.schemas import RejectedStationMessage

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
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

    def __init__(self) -> None:
        """Initialize the normalizer worker."""
        self.consumer = RabbitMQConsumer()
        self.publisher = RabbitMQClient()
        self.factory = TransformerFactory()
        self.messages_processed = 0
        self.messages_failed = 0
        self.messages_rejected = 0
        self.stations_rejected = 0

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

    async def process_message(self, message: dict[str, Any]) -> None:
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
        gateway_ingested_at = message.get("ingested_at")
        parent_message_id = message.get("parent_message_id")
        station_sequence = message.get("station_sequence")
        total_stations = message.get("total_stations")

        # TIMING: Capturar cuando inicia el normalizer
        normalizer_started_at = datetime.now(timezone.utc)

        logger.info(
            f"📥 Processing message {message_id} | " f"source={source} | format={data_format}"
        )

        try:
            # Validate message structure
            if not source or not payload:
                raise ValueError(f"Invalid message structure: missing source or payload")
            if source not in {"catalunya", "valencia", "galicia"}:
                raise ValueError(f"Invalid source in message: {source}")
            if data_format not in {"json", "xml", "csv"}:
                raise ValueError(f"Invalid format in message: {data_format}")

            source_lit = cast(Literal["catalunya", "valencia", "galicia"], source)
            format_lit = cast(Literal["json", "xml", "csv"], data_format)

            # Get appropriate transformer for this source
            normalization_mode = settings.NORMALIZATION_MODE
            transformer = self.factory.create(source, normalization_mode=normalization_mode)

            logger.debug(
                f"Using {transformer.__class__.__name__} for source={source} "
                f"(mode={normalization_mode})"
            )

            # Transform raw data to normalized format.
            # A raw message must represent exactly one station.
            normalized_stations = transformer.transform(payload)
            fuzzy_metrics = getattr(transformer, "last_metrics", None)
            if isinstance(fuzzy_metrics, dict):
                logger.info(f"Fuzzy transform metrics for message {message_id}: {fuzzy_metrics}")

            # Publish station-level rejected fragments captured by transformer
            raw_transformer_rejections: object = getattr(transformer, "rejected_items", [])
            transformer_rejections: list[dict[str, object]] = []
            if isinstance(raw_transformer_rejections, list):
                for item in cast(list[object], raw_transformer_rejections):
                    if isinstance(item, dict):
                        transformer_rejections.append(cast(dict[str, object], item))
            for rejected in transformer_rejections:
                reason = str(rejected.get("reason", "station_filtered"))
                raw_fragment: object | None = rejected.get("raw_fragment")
                if not isinstance(raw_fragment, (dict, str)):
                    raw_fragment = str(raw_fragment)
                await self._publish_rejected(
                    message_id=message_id,
                    source=source_lit,
                    data_format=format_lit,
                    reason=reason,
                    rejection_level="station",
                    raw_payload=raw_fragment,
                )
            self.stations_rejected += len(transformer_rejections)

            if not normalized_stations:
                logger.warning(f"⚠️  No stations extracted from message {message_id}")
                if not transformer_rejections:
                    await self._publish_rejected(
                        message_id=message_id,
                        source=source_lit,
                        data_format=format_lit,
                        reason="no_stations_extracted",
                        rejection_level="message",
                        raw_payload=payload,
                    )
                    self.messages_rejected += 1
                self.messages_processed += 1
                return

            if len(normalized_stations) > 1:
                raise ValueError(
                    f"Invalid raw work unit for message {message_id}: expected 1 station, "
                    f"got {len(normalized_stations)}"
                )

            logger.info(f"✅ Transformed {len(normalized_stations)} stations from {source}")

            # TIMING: Capturar cuando finaliza la transformación
            normalizer_completed_at = datetime.now(timezone.utc)

            station = normalized_stations[0]

            # Enriquecer el mensaje con timing information
            station_dict = station.model_dump(mode="json")
            timing_context: dict[str, object] = {
                "message_id": message_id,
                "normalizer_started_at": normalizer_started_at.isoformat(),
                "normalizer_completed_at": normalizer_completed_at.isoformat(),
            }
            if isinstance(gateway_ingested_at, str):
                timing_context["gateway_ingested_at"] = gateway_ingested_at
            if isinstance(parent_message_id, str):
                timing_context["parent_message_id"] = parent_message_id
            if isinstance(station_sequence, int):
                timing_context["station_sequence"] = station_sequence
            if isinstance(total_stations, int):
                timing_context["total_stations"] = total_stations

            station_dict["_timing_context"] = timing_context

            await self.publisher.publish(
                message=station_dict,
                exchange_name="normalized_data",
                routing_key="itv_stations",
            )

            logger.info(
                f"📤 Published station {station.station_id} "
                f"to normalized_data exchange"
            )

            self.messages_processed += 1

            # Log progress every 10 messages
            if self.messages_processed % 10 == 0:
                logger.info(
                    f"📊 Progress: {self.messages_processed} processed, "
                    f"{self.messages_failed} failed, "
                    f"{self.messages_rejected} messages rejected, "
                    f"{self.stations_rejected} stations rejected"
                )

        except ValueError as e:
            # Validation or transformation error - log and fail
            logger.error(f"❌ Validation error for message {message_id}: {e}")
            self.messages_failed += 1
            raise  # Re-raise to send to DLQ

        except Exception as e:
            # Unexpected error - log and fail
            logger.error(f"❌ Error processing message {message_id}: {e}", exc_info=True)
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
        logger.info(f"  - Messages rejected: {self.messages_rejected}")
        logger.info(f"  - Stations rejected: {self.stations_rejected}")
        logger.info("=" * 60)

        try:
            await self.consumer.disconnect()
            await self.publisher.disconnect()
            logger.info("✅ Shutdown complete")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}", exc_info=True)

    async def _publish_rejected(
        self,
        message_id: str,
        source: Literal["catalunya", "valencia", "galicia"],
        data_format: Literal["json", "xml", "csv"],
        reason: str,
        rejection_level: Literal["message", "station"],
        raw_payload: dict[str, Any] | str,
    ) -> None:
        """Publish filtered records for traceability and future retries."""
        try:
            rejected = RejectedStationMessage(
                message_id=message_id,
                source=source,
                format=data_format,
                reason=reason,
                rejection_level=rejection_level,
                raw_payload=raw_payload,
            )
            await self.publisher.publish(
                message=rejected.model_dump(mode="json"),
                exchange_name="rejected_data",
                routing_key="itv_stations",
            )
        except Exception as e:
            logger.error(
                f"Failed to publish rejected payload for message {message_id}: {e}",
                exc_info=True,
            )


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
