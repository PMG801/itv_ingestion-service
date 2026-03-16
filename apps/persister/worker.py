"""
Persister Worker
Consumes normalized data from RabbitMQ and persists it to PostgreSQL.

Este worker es el último paso del pipeline:
1. Consume mensajes de la cola 'normalized_data_queue'
2. Convierte NormalizedStation (Pydantic) a EstacionITV (ORM)
3. Realiza UPSERT en PostgreSQL (ON CONFLICT UPDATE)
4. Registra en ingestion_log el resultado del procesamiento
"""
import asyncio
import json
import logging

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


class PersisterWorker:
    """
    Worker que persiste datos normalizados en PostgreSQL.
    
    Implementa patrón UPSERT para evitar duplicados basándose en
    el constraint único (fuente_origen, id_en_fuente).
    """
    
    def __init__(self):
        self.rabbitmq_url = settings.RABBITMQ_URL
        self.queue_name = "normalized_data.itv_stations"
        self.connection: AbstractRobustConnection | None = None
        self.channel: AbstractChannel | None = None
        self._running = False

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
            self.rabbitmq_url,
            client_properties={"connection_name": "persister-worker"}
        )
        self.channel = await self.connection.channel()
        await self.channel.set_qos(prefetch_count=10)  # Procesar max 10 mensajes concurrentes
        logger.info("✓ Conectado a RabbitMQ")
    
    async def process_message(self, message: AbstractIncomingMessage) -> None:
        """
        Procesa un mensaje de la cola: deserializa, mapea y persiste.
        
        Args:
            message: Mensaje RabbitMQ con datos normalizados
        """
        message_id = message.message_id or "unknown"
        
        async with message.process(ignore_processed=True):
            try:
                # ================================================================
                # 1. Deserializar mensaje a NormalizedStation
                # ================================================================
                body = message.body.decode("utf-8")
                data = json.loads(body)
                if not isinstance(data, dict):
                    raise ValueError("Normalized message payload must be a JSON object")
                
                logger.debug(f"Procesando mensaje {message_id}: {data.get('station_id')}")
                
                # Validar con Pydantic
                normalized_station = NormalizedStation(**data)
                
                # ================================================================
                # 2. Convertir a ORM usando mapper
                # ================================================================
                estacion_orm = normalized_station_to_orm(normalized_station)
                
                # ================================================================
                # 3. UPSERT en PostgreSQL
                # ================================================================
                async with AsyncSessionLocal() as session:
                    try:
                        # Construir statement de INSERT con ON CONFLICT
                        stmt = insert(EstacionITV).values(
                            fuente_origen=estacion_orm.fuente_origen,
                            id_en_fuente=estacion_orm.id_en_fuente,
                            nombre=estacion_orm.nombre,
                            latitud=estacion_orm.latitud,
                            longitud=estacion_orm.longitud,
                            location=estacion_orm.location,
                            telefono=estacion_orm.telefono,
                            email=estacion_orm.email,
                            direccion=estacion_orm.direccion,
                            codigo_postal=estacion_orm.codigo_postal,
                            datos_extra=estacion_orm.datos_extra,
                            fecha_creacion=estacion_orm.fecha_creacion,
                            fecha_actualizacion=estacion_orm.fecha_actualizacion,
                        )
                        
                        # ON CONFLICT: actualizar todos los campos excepto PK y fecha_creacion
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
                                # fecha_actualizacion se actualiza automáticamente por trigger
                            }
                        )
                        
                        # Ejecutar UPSERT
                        await session.execute(stmt)
                        
                        # ========================================================
                        # 4. Registrar en ingestion_log
                        # ========================================================
                        log_entry = IngestionLog(
                            message_id=message_id,
                            domain="itv_stations",
                            source_system=normalized_station.source_system,
                            status="success",
                            error_message=None,
                        )
                        session.add(log_entry)
                        
                        await session.commit()
                        
                        logger.info(
                            f"✓ Estación persistida: {estacion_orm.nombre} "
                            f"({estacion_orm.fuente_origen}/{estacion_orm.id_en_fuente})"
                        )
                        
                        # ACK del mensaje (procesamiento exitoso)
                        await message.ack()
                    
                    except SQLAlchemyError as db_error:
                        await session.rollback()
                        logger.error(f"Error de BD al persistir mensaje {message_id}: {db_error}")
                        
                        # Registrar el fallo en ingestion_log
                        try:
                            log_entry = IngestionLog(
                                message_id=message_id,
                                domain="itv_stations",
                                source_system=normalized_station.source_system,
                                status="failed",
                                error_message=str(db_error)[:500],  # Truncar si es muy largo
                            )
                            session.add(log_entry)
                            await session.commit()
                        except Exception as log_error:
                            logger.error(f"No se pudo registrar error en ingestion_log: {log_error}")
                        
                        # NACK para reintentar (irá a DLQ si supera max_retries)
                        await message.nack(requeue=False)
            
            except json.JSONDecodeError as e:
                logger.error(f"JSON inválido en mensaje {message_id}: {e}")
                await message.nack(requeue=False)  # No reintentar JSON malformado
            
            except Exception as e:
                logger.exception(f"Error inesperado procesando mensaje {message_id}: {e}")
                await message.nack(requeue=False)
    
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
            }
        )
        
        logger.info(f"Esperando mensajes en cola '{self.queue_name}'...")
        self._running = True
        
        # Consumir mensajes
        await queue.consume(self.process_message)
    
    async def stop(self) -> None:
        """Detiene el worker gracefully."""
        logger.info("Deteniendo Persister Worker...")
        self._running = False
        
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
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Ejecutar worker async
    asyncio.run(main())

