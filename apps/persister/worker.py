"""
Persister Worker
Consumes normalized data from RabbitMQ and persists it to PostgreSQL.

Este worker es el último paso del pipeline:
1. Consume mensajes de la cola 'normalized_data_queue'
2. Convierte NormalizedStation (Pydantic) a EstacionITV (ORM)
3. Realiza UPSERT en PostgreSQL (ON CONFLICT UPDATE)
4. Registra en ingestion_log el resultado del procesamiento
   - Incluye timing information para benchmarking
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from aio_pika import connect_robust
from aio_pika.abc import AbstractChannel, AbstractIncomingMessage, AbstractRobustConnection
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError

from core.config import settings
from core.database import AsyncSessionLocal
from domain.itv_stations.schemas import NormalizedStation
from domain.itv_stations.mappers import normalized_station_to_orm
from domain.itv_stations.models import EstacionITV, IngestionLog

logger = logging.getLogger(__name__)


@dataclass
class BatchItem:
    """Represents one queued normalized station pending batch persistence."""

    message: AbstractIncomingMessage
    normalized_station: NormalizedStation
    timing_context: dict[str, Any]
    tracing_message_id: str


class PersisterWorker:
    """
    Worker que persiste datos normalizados en PostgreSQL.

    Implementa patrón UPSERT para evitar duplicados basándose en
    el constraint único (fuente_origen, id_en_fuente).
    """

    def __init__(self) -> None:
        self.rabbitmq_url = settings.RABBITMQ_URL
        self.queue_name = "normalized_data.itv_stations"
        self.batch_size = max(1, settings.PERSISTER_BATCH_SIZE)
        self.batch_timeout_ms = max(1, settings.PERSISTER_BATCH_TIMEOUT_MS)
        self.retry_max_attempts = max(1, settings.PERSISTER_RETRY_MAX_ATTEMPTS)
        self.retry_base_delay_ms = max(1, settings.PERSISTER_RETRY_BASE_DELAY_MS)
        self.connection: AbstractRobustConnection | None = None
        self.channel: AbstractChannel | None = None
        self._running = False
        self._buffer: list[BatchItem] = []
        self._buffer_lock = asyncio.Lock()
        self._flush_timer_task: asyncio.Task[None] | None = None

    @property
    def is_running(self) -> bool:
        return self._running

    def _require_channel(self) -> AbstractChannel:
        if self.channel is None:
            raise RuntimeError("RabbitMQ channel is not initialized")
        return self.channel

    async def connect_rabbitmq(self) -> None:
        """Establece conexión con RabbitMQ."""
        logger.info(f"Conectando a RabbitMQ: {self.rabbitmq_url}")
        self.connection = await connect_robust(
            self.rabbitmq_url, client_properties={"connection_name": "persister-worker"}
        )
        self.channel = await self.connection.channel()
        await self.channel.set_qos(prefetch_count=max(10, self.batch_size * 2))
        logger.info("✓ Conectado a RabbitMQ")

    async def process_message(self, message: AbstractIncomingMessage) -> None:
        """
        Procesa un mensaje de la cola: deserializa, mapea y persiste.

        Captura tiempos para cada etapa del pipeline y los almacena en
        ingestion_log.metadata para benchmarking.

        Args:
            message: Mensaje RabbitMQ con datos normalizados
        """
        try:
            body = message.body.decode("utf-8")
            data = json.loads(body)
            if not isinstance(data, dict):
                raise ValueError("Normalized message payload must be a JSON object")

            timing_context = data.pop("_timing_context", {})
            if not isinstance(timing_context, dict):
                timing_context = {}

            normalized_station = NormalizedStation(**data)
            tracing_message_id = str(timing_context.get("message_id") or message.message_id or "")
            if not tracing_message_id:
                fallback_ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
                tracing_message_id = (
                    f"fallback-{normalized_station.source_system}-"
                    f"{normalized_station.raw_id or normalized_station.station_id}-"
                    f"{fallback_ts}"
                )

            await self._enqueue_item(
                BatchItem(
                    message=message,
                    normalized_station=normalized_station,
                    timing_context=timing_context,
                    tracing_message_id=tracing_message_id,
                )
            )

        except json.JSONDecodeError as e:
            logger.error(f"JSON inválido en mensaje {message.message_id or 'unknown'}: {e}")
            await message.nack(requeue=False)
        except Exception as e:
            logger.exception(f"Error inesperado procesando mensaje {message.message_id or 'unknown'}: {e}")
            await message.nack(requeue=False)

    async def _enqueue_item(self, item: BatchItem) -> None:
        should_flush = False
        async with self._buffer_lock:
            self._buffer.append(item)
            self._restart_flush_timer_locked()
            if len(self._buffer) >= self.batch_size:
                self._cancel_flush_timer_locked()
                should_flush = True

        if should_flush:
            await self._flush_batch(trigger="size")

    def _restart_flush_timer_locked(self) -> None:
        self._cancel_flush_timer_locked()
        self._flush_timer_task = asyncio.create_task(self._flush_after_timeout())

    def _cancel_flush_timer_locked(self) -> None:
        if self._flush_timer_task and not self._flush_timer_task.done():
            self._flush_timer_task.cancel()
        self._flush_timer_task = None

    async def _flush_after_timeout(self) -> None:
        try:
            await asyncio.sleep(self.batch_timeout_ms / 1000)
            await self._flush_batch(trigger="timeout")
        except asyncio.CancelledError:
            return

    async def _flush_batch(self, trigger: str) -> None:
        async with self._buffer_lock:
            if not self._buffer:
                return
            batch_items = list(self._buffer)
            self._buffer.clear()
            self._cancel_flush_timer_locked()

        batch_id = datetime.now(timezone.utc).strftime("batch-%Y%m%d%H%M%S%f")
        logger.info(
            f"Flushing batch {batch_id} with {len(batch_items)} stations (trigger={trigger})"
        )

        last_error: Exception | None = None
        for attempt in range(1, self.retry_max_attempts + 1):
            try:
                await self._persist_batch(batch_items=batch_items, batch_id=batch_id)
                for item in batch_items:
                    await item.message.ack()
                logger.info(
                    f"✓ Batch {batch_id} persisted successfully "
                    f"({len(batch_items)} stations, attempt={attempt})"
                )
                return
            except Exception as error:
                last_error = error
                logger.error(
                    f"Batch {batch_id} failed on attempt {attempt}/{self.retry_max_attempts}: {error}",
                    exc_info=True,
                )
                if attempt < self.retry_max_attempts:
                    delay = (self.retry_base_delay_ms * (2 ** (attempt - 1))) / 1000
                    await asyncio.sleep(delay)

        await self._record_failed_batch(batch_items=batch_items, batch_id=batch_id, error=last_error)

        # Retries exhausted: move the full batch to DLQ preserving atomic behavior.
        for item in batch_items:
            await item.message.nack(requeue=False)

    async def _persist_batch(self, batch_items: list[BatchItem], batch_id: str) -> None:
        persister_started_at = datetime.now(timezone.utc)

        rows: list[dict[str, Any]] = []
        for item in batch_items:
            estacion_orm = normalized_station_to_orm(item.normalized_station)
            rows.append(
                {
                    "fuente_origen": estacion_orm.fuente_origen,
                    "id_en_fuente": estacion_orm.id_en_fuente,
                    "nombre": estacion_orm.nombre,
                    "latitud": estacion_orm.latitud,
                    "longitud": estacion_orm.longitud,
                    "location": estacion_orm.location,
                    "telefono": estacion_orm.telefono,
                    "email": estacion_orm.email,
                    "direccion": estacion_orm.direccion,
                    "codigo_postal": estacion_orm.codigo_postal,
                    "datos_extra": estacion_orm.datos_extra,
                    "fecha_creacion": estacion_orm.fecha_creacion,
                    "fecha_actualizacion": estacion_orm.fecha_actualizacion,
                }
            )

        async with AsyncSessionLocal() as session:
            try:
                stmt = insert(EstacionITV).values(rows)
                stmt = stmt.on_conflict_do_update(
                    constraint="uq_estaciones_fuente_id",
                    set_={
                        "nombre": stmt.excluded.nombre,
                        "latitud": stmt.excluded.latitud,
                        "longitud": stmt.excluded.longitud,
                        "location": stmt.excluded.location,
                        "telefono": stmt.excluded.telefono,
                        "email": stmt.excluded.email,
                        "direccion": stmt.excluded.direccion,
                        "codigo_postal": stmt.excluded.codigo_postal,
                        "datos_extra": stmt.excluded.datos_extra,
                    },
                )
                await session.execute(stmt)

                persister_completed_at = datetime.now(timezone.utc)
                persister_duration_ms = int(
                    (persister_completed_at - persister_started_at).total_seconds() * 1000
                )

                for item in batch_items:
                    log_entry = IngestionLog(
                        message_id=item.tracing_message_id,
                        domain="itv_stations",
                        source_system=item.normalized_station.source_system,
                        status="success",
                        error_message=None,
                    )
                    log_entry.metadata_json = {
                        "timing": {
                            "gateway_ingested_at": item.timing_context.get("gateway_ingested_at"),
                            "normalizer_started_at": item.timing_context.get("normalizer_started_at"),
                            "normalizer_completed_at": item.timing_context.get("normalizer_completed_at"),
                            "persister_started_at": persister_started_at.isoformat(),
                            "persister_completed_at": persister_completed_at.isoformat(),
                            "persister_duration_ms": persister_duration_ms,
                        },
                        "batch": {
                            "batch_id": batch_id,
                            "batch_size": len(batch_items),
                            "parent_message_id": item.timing_context.get("parent_message_id"),
                            "station_sequence": item.timing_context.get("station_sequence"),
                            "total_stations": item.timing_context.get("total_stations"),
                        },
                    }
                    session.add(log_entry)

                await session.commit()
            except SQLAlchemyError:
                await session.rollback()
                raise

    async def _record_failed_batch(
        self,
        batch_items: list[BatchItem],
        batch_id: str,
        error: Exception | None,
    ) -> None:
        error_msg = str(error)[:500] if error else "unknown_batch_persistence_error"
        persister_completed_at = datetime.now(timezone.utc)

        try:
            async with AsyncSessionLocal() as session:
                for item in batch_items:
                    log_entry = IngestionLog(
                        message_id=item.tracing_message_id,
                        domain="itv_stations",
                        source_system=item.normalized_station.source_system,
                        status="failed",
                        error_message=error_msg,
                    )
                    log_entry.metadata_json = {
                        "timing": {
                            "gateway_ingested_at": item.timing_context.get("gateway_ingested_at"),
                            "normalizer_started_at": item.timing_context.get("normalizer_started_at"),
                            "normalizer_completed_at": item.timing_context.get("normalizer_completed_at"),
                            "persister_completed_at": persister_completed_at.isoformat(),
                        },
                        "batch": {
                            "batch_id": batch_id,
                            "batch_size": len(batch_items),
                            "retry_attempts": self.retry_max_attempts,
                        },
                        "error_in_step": "batch_persistence",
                    }
                    session.add(log_entry)

                await session.commit()
        except SQLAlchemyError as log_error:
            logger.error(f"No se pudo registrar error de batch en ingestion_log: {log_error}")

    async def start_consuming(self) -> None:
        """Inicia el consumo de mensajes de RabbitMQ."""
        await self.connect_rabbitmq()

        # Declarar la cola — los argumentos deben coincidir EXACTAMENTE con los
        # usados al crearla (definitions.json), si no RabbitMQ lanza PRECONDITION_FAILED.
        channel = self._require_channel()
        queue = await channel.declare_queue(
            self.queue_name,
            durable=True,
            arguments={
                "x-dead-letter-exchange": "dlx",
                "x-dead-letter-routing-key": "dlx.normalized_data.itv_stations",
            },
        )

        logger.info(f"Esperando mensajes en cola '{self.queue_name}'...")
        logger.info(
            f"Batching config -> size={self.batch_size}, timeout_ms={self.batch_timeout_ms}, "
            f"retry_attempts={self.retry_max_attempts}"
        )
        self._running = True

        # Consumir mensajes
        await queue.consume(self.process_message)

    async def stop(self) -> None:
        """Detiene el worker gracefully."""
        logger.info("Deteniendo Persister Worker...")
        self._running = False

        async with self._buffer_lock:
            self._cancel_flush_timer_locked()
        await self._flush_batch(trigger="shutdown")

        if self.channel:
            await self.channel.close()
        if self.connection:
            await self.connection.close()

        logger.info("✓ Persister Worker detenido")


async def main():
    """Main worker loop."""
    logger.info("Persister worker starting...")

    worker = PersisterWorker()

    try:
        await worker.start_consuming()

        # Mantener el worker corriendo hasta Ctrl+C
        while worker.is_running:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        logger.info("Señal de interrupción recibida (Ctrl+C)")
    except Exception as e:
        logger.exception(f"Error fatal en Persister Worker: {e}")
    finally:
        await worker.stop()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Ejecutar worker async
    asyncio.run(main())
