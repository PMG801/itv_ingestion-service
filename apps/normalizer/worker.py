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
from dataclasses import dataclass
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Literal, cast

from aio_pika.abc import AbstractIncomingMessage

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


@dataclass(slots=True)
class _BatchItem:
    message: AbstractIncomingMessage
    payload: dict[str, Any]


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
        self._batch_size = max(1, settings.LLM_NORMALIZER_BATCH_SIZE)
        self._batch_timeout_ms = max(1, settings.LLM_NORMALIZER_BATCH_TIMEOUT_MS)
        self._batch_buffer: list[_BatchItem] = []
        self._batch_lock = asyncio.Lock()
        self._batch_timer_task: asyncio.Task[None] | None = None

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
            if settings.NORMALIZATION_MODE.upper() == "LLM":
                logger.info(
                    "LLM batch config -> size=%s, timeout_ms=%s",
                    self._batch_size,
                    self._batch_timeout_ms,
                )

            # DLX configuration - must match queue creation arguments
            dlx_args = {
                "x-dead-letter-exchange": "dlx",
                "x-dead-letter-routing-key": "dlx.raw_data.itv_stations",
            }

            # Start consuming messages
            await self.consumer.consume_raw(
                queue_name="raw_data.itv_stations",
                callback=self._enqueue_message_for_batch,
                # Manual ACK/REJECT is handled in normalizer callbacks (single + batch paths).
                # auto_ack=True here disables wrapper-level ack/reject to avoid double-processing.
                auto_ack=True,
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
        injection_type = message.get("injection_type")
        injection_metadata = message.get("injection_metadata")

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
            llm_mode = normalization_mode.upper() == "LLM"
            llm_inference_start_ts: datetime | None = None
            llm_inference_end_ts: datetime | None = None
            llm_inference_elapsed_ms: float | None = None

            logger.debug(
                f"Using {transformer.__class__.__name__} for source={source} "
                f"(mode={normalization_mode})"
            )

            # Transform raw data to normalized format.
            # A raw message must represent exactly one station.
            if llm_mode:
                llm_inference_start_ts = datetime.now(timezone.utc)
                llm_perf_start = perf_counter()
            if llm_mode and hasattr(transformer, "transform_async"):
                transform_async = getattr(transformer, "transform_async")
                normalized_stations = await transform_async(payload)
            else:
                normalized_stations = transformer.transform(payload)
            if llm_mode:
                llm_inference_end_ts = datetime.now(timezone.utc)
                llm_inference_elapsed_ms = round((perf_counter() - llm_perf_start) * 1000, 3)

            transformer_metrics = getattr(transformer, "last_metrics", None)
            if isinstance(transformer_metrics, dict):
                logger.info(
                    f"Transformer metrics for message {message_id}: {transformer_metrics}"
                )

            if llm_mode:
                generated_mapping = getattr(transformer, "last_generated_mapping", None)
                if generated_mapping is not None:
                    payload_preview = str(payload)
                    mapping_preview = str(generated_mapping)
                    logger.debug(
                        "LLM mapping preview | message_id=%s | raw_payload=%s | mapped=%s",
                        message_id,
                        payload_preview[:1200],
                        mapping_preview[:1200],
                    )

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
                if llm_mode:
                    rejection_reason = "llm_transform_failed"
                    if isinstance(transformer_metrics, dict):
                        error_reason = transformer_metrics.get("llm_last_error_reason")
                        if isinstance(error_reason, str) and error_reason:
                            rejection_reason = error_reason
                    await self._publish_rejected(
                        message_id=message_id,
                        source=source_lit,
                        data_format=format_lit,
                        reason=rejection_reason,
                        rejection_level="message",
                        raw_payload=payload,
                    )
                    self.messages_rejected += 1
                elif not transformer_rejections:
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
            if isinstance(injection_type, str):
                timing_context["injection_type"] = injection_type
            if isinstance(injection_metadata, dict):
                timing_context["injection_metadata"] = injection_metadata
            if llm_mode and llm_inference_start_ts is not None:
                timing_context["llm_inference_start"] = llm_inference_start_ts.isoformat()
            if llm_mode and llm_inference_end_ts is not None:
                timing_context["llm_inference_end"] = llm_inference_end_ts.isoformat()
            if llm_mode and llm_inference_elapsed_ms is not None:
                timing_context["llm_inference_ms"] = llm_inference_elapsed_ms
            if llm_mode and isinstance(transformer_metrics, dict):
                llm_pydantic_errors = transformer_metrics.get("llm_pydantic_validation_errors")
                llm_token_usage = transformer_metrics.get("llm_token_usage")
                if isinstance(llm_pydantic_errors, int):
                    timing_context["llm_pydantic_validation_errors"] = llm_pydantic_errors
                if isinstance(llm_token_usage, int):
                    timing_context["llm_token_usage"] = llm_token_usage

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

    async def _enqueue_message_for_batch(
        self,
        message: AbstractIncomingMessage,
        payload: dict[str, Any],
    ) -> None:
        """Buffer messages for LLM batching, or process immediately for non-LLM."""
        if settings.NORMALIZATION_MODE.upper() != "LLM":
            await self._process_message_with_ack(message, payload)
            return

        item = _BatchItem(message=message, payload=payload)
        should_flush = False
        async with self._batch_lock:
            self._batch_buffer.append(item)
            self._restart_batch_timer_locked()
            if len(self._batch_buffer) >= self._batch_size:
                self._cancel_batch_timer_locked()
                batch_items = list(self._batch_buffer)
                self._batch_buffer.clear()
                should_flush = True

        if should_flush:
            await self._process_batch(batch_items, trigger="size")

    async def _process_message_with_ack(
        self,
        message: AbstractIncomingMessage,
        payload: dict[str, Any],
    ) -> None:
        try:
            await self.process_message(payload)
            await message.ack()
        except Exception:
            await message.reject(requeue=False)

    def _restart_batch_timer_locked(self) -> None:
        self._cancel_batch_timer_locked()
        self._batch_timer_task = asyncio.create_task(self._flush_after_timeout())

    def _cancel_batch_timer_locked(self) -> None:
        if self._batch_timer_task and not self._batch_timer_task.done():
            current_task = asyncio.current_task()
            if self._batch_timer_task is not current_task:
                self._batch_timer_task.cancel()
        self._batch_timer_task = None

    async def _flush_after_timeout(self) -> None:
        try:
            await asyncio.sleep(self._batch_timeout_ms / 1000)
            await self._flush_batch(trigger="timeout")
        except asyncio.CancelledError:
            return

    async def _flush_batch(self, trigger: str) -> None:
        async with self._batch_lock:
            if not self._batch_buffer:
                return
            batch_items = list(self._batch_buffer)
            self._batch_buffer.clear()
            self._cancel_batch_timer_locked()

        await self._process_batch(batch_items, trigger=trigger)

    async def _process_batch(self, batch_items: list[_BatchItem], trigger: str) -> None:
        if not batch_items:
            return

        logger.info(
            "🧺 Processing LLM batch size=%s trigger=%s",
            len(batch_items),
            trigger,
        )

        grouped: dict[str, list[tuple[_BatchItem, dict[str, Any]]]] = {}
        for item in batch_items:
            payload = item.payload
            try:
                source = payload.get("source")
                data_format = payload.get("format")
                raw_payload = payload.get("payload")
                if not source or raw_payload is None:
                    raise ValueError("Invalid message structure: missing source or payload")
                if source not in {"catalunya", "valencia", "galicia"}:
                    raise ValueError(f"Invalid source in message: {source}")
                if data_format not in {"json", "xml", "csv"}:
                    raise ValueError(f"Invalid format in message: {data_format}")
            except ValueError as exc:
                message_id = payload.get("message_id", "unknown")
                logger.error("❌ Validation error for message %s: %s", message_id, exc)
                self.messages_failed += 1
                await item.message.reject(requeue=False)
                continue

            grouped.setdefault(source, []).append((item, payload))

        for source, items in grouped.items():
            await self._process_source_batch(source, items)

    async def _process_source_batch(
        self,
        source: str,
        items: list[tuple[_BatchItem, dict[str, Any]]],
    ) -> None:
        if not items:
            return

        normalization_mode = settings.NORMALIZATION_MODE
        transformer = self.factory.create(source, normalization_mode=normalization_mode)
        normalizer_started_at = datetime.now(timezone.utc)
        llm_inference_start_ts: datetime | None = datetime.now(timezone.utc)
        llm_inference_end_ts: datetime | None = None
        llm_inference_elapsed_ms: float | None = None

        payloads = [payload["payload"] for _, payload in items]
        llm_perf_start = perf_counter()

        if hasattr(transformer, "transform_batch_async"):
            transform_batch_async = getattr(transformer, "transform_batch_async")
            normalized_stations = await transform_batch_async(payloads)
        else:
            normalized_stations = []
            for raw_payload in payloads:
                if hasattr(transformer, "transform_async"):
                    transform_async = getattr(transformer, "transform_async")
                    normalized_stations.extend(await transform_async(raw_payload))
                else:
                    normalized_stations.extend(transformer.transform(raw_payload))

        llm_inference_end_ts = datetime.now(timezone.utc)
        llm_inference_elapsed_ms = round((perf_counter() - llm_perf_start) * 1000, 3)

        transformer_metrics = getattr(transformer, "last_metrics", None)
        if isinstance(transformer_metrics, dict):
            logger.info(
                "Transformer metrics for batch (source=%s): %s",
                source,
                transformer_metrics,
            )

        if not normalized_stations:
            for item, payload in items:
                message_id = payload.get("message_id", "unknown")
                data_format = payload.get("format", "unknown")
                source_lit = cast(Literal["catalunya", "valencia", "galicia"], source)
                format_lit = cast(Literal["json", "xml", "csv"], data_format)
                raw_payload = payload.get("payload")
                await self._publish_rejected(
                    message_id=message_id,
                    source=source_lit,
                    data_format=format_lit,
                    reason="llm_transform_failed",
                    rejection_level="message",
                    raw_payload=raw_payload,
                )
                self.messages_rejected += 1
                self.messages_processed += 1
                await item.message.ack()
            return

        if len(normalized_stations) != len(items):
            logger.warning(
                "Batch mismatch for source=%s: expected=%s got=%s. "
                "Falling back to per-message processing.",
                source,
                len(items),
                len(normalized_stations),
            )
            for item, payload in items:
                await self._process_message_with_ack(item.message, payload)
            return

        try:
            for (item, payload), station in zip(items, normalized_stations):
                message_id = payload.get("message_id", "unknown")
                data_format = payload.get("format", "unknown")
                source_lit = cast(Literal["catalunya", "valencia", "galicia"], source)
                format_lit = cast(Literal["json", "xml", "csv"], data_format)
                raw_payload = payload.get("payload")
                gateway_ingested_at = payload.get("ingested_at")
                parent_message_id = payload.get("parent_message_id")
                station_sequence = payload.get("station_sequence")
                total_stations = payload.get("total_stations")
                injection_type = payload.get("injection_type")
                injection_metadata = payload.get("injection_metadata")

                if station is None:
                    await self._publish_rejected(
                        message_id=message_id,
                        source=source_lit,
                        data_format=format_lit,
                        reason="llm_transform_failed",
                        rejection_level="message",
                        raw_payload=raw_payload,
                    )
                    self.messages_rejected += 1
                    self.messages_processed += 1
                    await item.message.ack()
                    continue

                normalizer_completed_at = datetime.now(timezone.utc)
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
                if llm_inference_start_ts is not None:
                    timing_context["llm_inference_start"] = llm_inference_start_ts.isoformat()
                if llm_inference_end_ts is not None:
                    timing_context["llm_inference_end"] = llm_inference_end_ts.isoformat()
                if llm_inference_elapsed_ms is not None:
                    timing_context["llm_inference_ms"] = llm_inference_elapsed_ms
                if isinstance(transformer_metrics, dict):
                    llm_pydantic_errors = transformer_metrics.get("llm_pydantic_validation_errors")
                    llm_token_usage = transformer_metrics.get("llm_token_usage")
                    if isinstance(llm_pydantic_errors, int):
                        timing_context["llm_pydantic_validation_errors"] = llm_pydantic_errors
                    if isinstance(llm_token_usage, int):
                        timing_context["llm_token_usage"] = llm_token_usage

                station_dict["_timing_context"] = timing_context

                await self.publisher.publish(
                    message=station_dict,
                    exchange_name="normalized_data",
                    routing_key="itv_stations",
                )

                logger.info(
                    "📤 Published station %s to normalized_data exchange",
                    station.station_id,
                )

                self.messages_processed += 1
                await item.message.ack()

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
            await self._flush_batch(trigger="shutdown")
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
