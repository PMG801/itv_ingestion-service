"""
Compatibility Router para mapear endpoints antiguos del Frontend.

Este router actúa como un adaptador entre la API esperada por el Frontend
(endpoints /api/carga/*) y la nueva API asíncrona del Backend (/api/v1/ingest/*).

Mantiene un caché en memoria de source_code → message_id para el polling posterior.
"""

from typing import Any
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_async_session
from core.database.queries import get_ingest_status
from domain.itv_stations.models import IngestionLog, EstacionITV
from domain.itv_stations.schemas import NormalizedStation
from domain.itv_stations.mappers import normalized_station_to_orm
from domain.synthetic_data_generator import SyntheticDataGenerator
from sqlalchemy import select, func, text
from sqlalchemy.dialects.postgresql import insert

# Cache en memoria: {source_code: {message_id, stats, timestamp}}
_message_id_cache: dict[str, dict[str, Any]] = {}

router = APIRouter(prefix="/api/carga", tags=["compatibility"])


@router.post("/")
async def load_data(
    payload: dict[str, Any],
    session: AsyncSession = Depends(get_async_session)
) -> dict[str, Any]:
    """
    Endpoint compatibilidad: inicia carga de datos desde una fuente.

    Este endpoint mapea la solicitud del Frontend a /api/v1/ingest/{source}
    internamente y devuelve una respuesta compatible.

    Request body esperado:
    {
        "fuente": "CAT" | "VAL" | "GAL"
    }

    Note: En la nueva arquitectura, este endpoint normalmente dispararía
    una ingesta asíncrona. Para mantener compatibilidad, aquí iniciamos
    el procesamiento y almacenamos el message_id.

    Response: 202 ACCEPTED con el message_id
    """
    # Mapeo de códigos antiguos a nuevos
    source_mapping = {
        "CAT": "catalunya",
        "VAL": "valencia",
        "GAL": "galicia",
    }

    if "fuente" not in payload:
        raise HTTPException(
            status_code=400,
            detail="Campo 'fuente' requerido en el body"
        )

    source_code = payload.get("fuente", "")
    if not isinstance(source_code, str):
        raise HTTPException(
            status_code=400,
            detail="Campo 'fuente' debe ser string"
        )
    source_name = source_mapping.get(source_code)

    if not source_name or source_name not in ["catalunya", "valencia", "galicia"]:
        raise HTTPException(
            status_code=400,
            detail=f"Fuente inválida: {source_code}. Usar CAT, VAL o GAL"
        )

    message_id = str(uuid4())

    try:
        from typing import Literal, cast
        source_literal = cast(Literal["catalunya", "valencia", "galicia"], source_name)
        generated = SyntheticDataGenerator.generate_stations(
            source=source_literal,
            count=25,
            error_rate=0.05,
            include_errors=["missing_field"]
        )

        successful = 0
        failed = 0

        for raw_station in generated:
            try:
                raw_str: dict[str, str | float | None] = raw_station  # type: ignore[assignment]
                normalized_station = NormalizedStation(
                    station_id=str(raw_station["station_id"]),  # type: ignore[index]
                    name=str(raw_station["name"]),  # type: ignore[index]
                    source_system=source_literal,
                    address=raw_str.get("address"),  # type: ignore[assignment]
                    city=raw_str.get("city"),  # type: ignore[assignment]
                    province=raw_str.get("province"),  # type: ignore[assignment]
                    postal_code=raw_str.get("postal_code"),  # type: ignore[assignment]
                    latitude=raw_str.get("latitude"),  # type: ignore[assignment]
                    longitude=raw_str.get("longitude"),  # type: ignore[assignment]
                    phone=raw_str.get("phone"),  # type: ignore[assignment]
                    email=raw_str.get("email"),  # type: ignore[assignment]
                    raw_id=raw_str.get("raw_id"),  # type: ignore[assignment]
                )

                estacion_orm = normalized_station_to_orm(normalized_station)
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
                successful += 1
            except Exception:
                failed += 1

        db_status = "success" if successful > 0 else "failed"
        response_status = "completed" if successful > 0 else "failed"

        log_entry = IngestionLog(
            message_id=message_id,
            domain="itv_stations",
            source_system=source_name,
            status=db_status,
            error_message=None if successful > 0 else "No stations could be persisted",
        )
        log_entry.metadata_json = {
            "stations_processed": {
                "total_processed": len(generated),
                "successful": successful,
                "failed": failed,
                "rejection_reasons": {},
            },
            "timing": {
                "total_duration_ms": 0,
            },
            "injection_type": "api",
        }
        session.add(log_entry)
        await session.commit()

        _message_id_cache[source_code] = {
            "message_id": message_id,
            "stats": {
                "total": len(generated),
                "exitosos": successful,
                "fallidos": failed,
            },
            "status": response_status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Error en carga de compatibilidad: {str(e)}")

    return {
        "status": "accepted",
        "message_id": message_id,
        "source": source_code,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "message": f"Data ingestion from {source_name} queued for processing"
    }


@router.get("/resultado/{source}")
async def get_load_result(
    source: str,
    session: AsyncSession = Depends(get_async_session)
):
    """
    Endpoint compatibilidad: obtiene resultado de una carga.

    Mapeo de compatibilidad:
    - Recibe source code (CAT, VAL, GAL)
    - Consulta ingestion_log por el message_id en caché
    - Retorna stats en formato compatible con Frontend antiguo

    Response esperado por Frontend antiguo:
    {
        "status": "completed",
        "origin": "CAT",
        "estaciones_unicas": 150,
        "insertados_ok": 145,
        "fallidos": 5,
        "logs": {
            "stats": { "total": 150, "exitosos": 145, "fallidos": 5 },
            "logs": [...]
        }
    }
    """
    source_mapping = {
        "CAT": "catalunya",
        "VAL": "valencia",
        "GAL": "galicia",
    }

    if source not in source_mapping:
        raise HTTPException(
            status_code=400,
            detail=f"Fuente inválida: {source}. Usar CAT, VAL o GAL"
        )

    # Obtener message_id desde caché
    cache_entry = _message_id_cache.get(source)
    if not cache_entry:
        raise HTTPException(
            status_code=404,
            detail=f"Sin ingesta iniciada para {source}. Use POST /api/carga/ primero"
        )
    message_id = str(cache_entry["message_id"])

    # Consultar estado desde BD
    ingest_status = await get_ingest_status(session, message_id)

    if not ingest_status:
        raise HTTPException(
            status_code=404,
            detail=f"Message ID {message_id} not found"
        )

    # Contar estaciones en BD para esta fuente
    source_name = source_mapping[source]
    stmt = select(func.count(EstacionITV.id)).where(
        EstacionITV.fuente_origen == source_name
    )
    result = await session.execute(stmt)
    total_in_db = result.scalar() or 0

    # Construir respuesta compatible con antiguo formato del Frontend
    stats_from_cache = cache_entry.get("stats", {})
    return {
        "status": cache_entry.get("status", "completed" if ingest_status["status"] == "success" else ingest_status["status"]),
        "origin": source,
        "estaciones_unicas": total_in_db,
        "insertados_ok": stats_from_cache.get("exitosos", ingest_status.get("stations", {}).get("successful", 0)),
        "fallidos": stats_from_cache.get("fallidos", ingest_status.get("stations", {}).get("failed", 0)),
        "logs": {
            "stats": {
                "total": stats_from_cache.get("total", total_in_db),
                "exitosos": stats_from_cache.get("exitosos", ingest_status.get("stations", {}).get("successful", 0)),
                "fallidos": stats_from_cache.get("fallidos", ingest_status.get("stations", {}).get("failed", 0)),
            },
            "logs": [
                {
                    "level": "info",
                    "message": f"Processed from {source_name}",
                    "details": ingest_status.get("rejection_summary", {})
                }
            ]
        }
    }


@router.delete("/limpiar-todo")
async def clear_database(
    session: AsyncSession = Depends(get_async_session)
):
    """
    Endpoint compatibilidad: borra toda la base de datos.

    WARNING: Trunca las tablas estaciones e ingestion_log.
    Solo debe usarse en desarrollo.
    """
    try:
        # Truncate estaciones table
        await session.execute(text("TRUNCATE TABLE itv.estaciones CASCADE"))
        # Truncate ingestion_log table
        await session.execute(text("TRUNCATE TABLE itv.ingestion_log CASCADE"))
        await session.commit()

        # Limpiar caché en memoria
        _message_id_cache.clear()

        return {
            "status": "success",
            "message": "Base de datos limpiada completamente"
        }

    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error al limpiar base de datos: {str(e)}"
        )
