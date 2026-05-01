"""
Monitoring Router para exponer estado y métricas del sistema.

Proporciona endpoints para que el Frontend consulte:
1. Estado de una ingesta específica (GET /api/v1/monitoring/ingest/{message_id})
2. Métricas agregadas del sistema (GET /api/v1/monitoring/metrics)
"""

from typing import Any
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from core.database import get_async_session
from core.database.queries import (
    get_ingest_status,
    get_metrics_aggregation,
    deactivate_llm_mapping_rule_by_key,
)

router = APIRouter(prefix="/api/v1/monitoring", tags=["monitoring"])


@router.get("/ingest/{message_id}")
async def get_ingest_status_endpoint(
    message_id: str, session: AsyncSession = Depends(get_async_session)
) -> dict[str, Any]:
    """
    Obtiene el estado completo de una ingesta específica.

    Incluye:
    - Status: processing, completed, failed
    - Timing breakdown: latencia de cada etapa en ms
    - Conteo de estaciones procesadas, exitosas, fallidas
    - Razones de rechazo
    - Tipo de inyección: api, file, synthetic

    Path Parameters:
        message_id: UUID único del mensaje

    Returns: {
        "message_id": "uuid",
        "status": "processing|completed|failed",
        "timing": {
            "gateway_latency_ms": 15,
            "normalizer_duration_ms": 1250,
            "persister_duration_ms": 320,
            "total_duration_ms": 1585
        },
        "stations": {
            "successful": 145,
            "failed": 5
        },
        "rejection_summary": {
            "total_stations": 150,
            "rejected_count": 5,
            "rejection_reasons": {"invalid_coordinates": 2, "duplicate": 3}
        },
        "injection_type": "api|file|synthetic",
        "processed_at": "2026-03-20T12:00:00+00:00"
    }

    HTTP Status:
        200: OK - Ingesta encontrada
        404: Not Found - Message ID no existe
    """
    status = await get_ingest_status(session, message_id)

    if not status:
        raise HTTPException(status_code=404, detail=f"Message ID '{message_id}' not found")

    return status


@router.get("/metrics")
async def get_metrics_endpoint(
    period_hours: int = Query(24, ge=1, le=8760), session: AsyncSession = Depends(get_async_session)
) -> dict[str, Any]:
    """
    Obtiene métricas agregadas del sistema en un período.

    Query Parameters:
        period_hours: Horas atrás a analizar (1-8760, default 24)

    Returns: {
        "total_messages": 1250,
        "successful": 1200,
        "failed": 50,
        "period_hours": 24,
        "avg_latency_ms": 1585.42,
        "p95_latency_ms": 2100.0,
        "p99_latency_ms": 2800.0,
        "per_source_stats": {
            "catalunya": {
                "total": 500,
                "successful": 490,
                "failed": 10
            },
            ...
        },
        "queue_depths": {
            "raw_data.itv_stations": 8,
            "normalized_data.itv_stations": 3,
            "rejected_data.itv_stations": 0
        },
        "top_rejection_reasons": [
            {"reason": "invalid_coordinates", "count": 35, "percentage": 70.0},
            {"reason": "duplicate_entry", "count": 10, "percentage": 20.0}
        ],
        "timestamp": "2026-03-20T18:30:00+00:00"
    }

    HTTP Status:
        200: OK - Métricas disponibles
    """
    metrics = await get_metrics_aggregation(session, period_hours)
    return metrics


@router.delete("/truncate")
async def truncate_storage_endpoint(
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """
    Trunca rápidamente las tablas principales del almacén de ingesta.

    Tablas afectadas:
    - itv.estaciones
    - itv.ingestion_log

    HTTP Status:
        200: Truncate completado
        500: Error durante la operación
    """
    try:
        await session.execute(text("TRUNCATE TABLE itv.estaciones CASCADE"))
        await session.execute(text("TRUNCATE TABLE itv.ingestion_log CASCADE"))
        await session.commit()

        return {
            "status": "success",
            "message": "Almacén truncado correctamente",
        }
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Error truncating storage: {str(e)}")


@router.delete("/llm-rules/{source_system}/{province_type}")
async def invalidate_llm_rule_endpoint(
    source_system: str,
    province_type: str,
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """
    Invalida una regla LLM activa para una combinación source_system + province_type.

    Esto fuerza que el siguiente batch para esa provincia regenere la regla
    mediante una nueva llamada al LLM en lugar de usar la caché.

    Path Parameters:
        source_system: Source system identifier (e.g., 'catalunya', 'valencia', 'galicia')
        province_type: Province type to invalidate (e.g., 'Barcelona', 'Valencia')

    Returns: {
        "status": "success" | "not_found",
        "message": "Rule invalidated" | "No active rule found",
        "deactivated_count": 0 | 1
    }

    HTTP Status:
        200: OK - Rule invalidated or not found
        400: Bad Request - Invalid source_system or province_type
        500: Internal Server Error
    """
    try:
        if not source_system or not province_type:
            raise HTTPException(
                status_code=400,
                detail="source_system and province_type are required",
            )

        deactivated_count = await deactivate_llm_mapping_rule_by_key(
            session, source_system, province_type
        )

        if deactivated_count == 0:
            return {
                "status": "not_found",
                "message": f"No active rule found for source_system={source_system}, province_type={province_type}",
                "deactivated_count": 0,
            }

        return {
            "status": "success",
            "message": f"Rule invalidated for source_system={source_system}, province_type={province_type}",
            "deactivated_count": deactivated_count,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error invalidating LLM rule: {str(e)}",
        )
