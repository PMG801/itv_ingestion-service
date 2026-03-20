"""
Monitoring Router para exponer métricas y estado del sistema.

Proporciona endpoints para que el Frontend consulte:
1. Estado de una ingesta específica (GET /api/v1/monitoring/ingest/{message_id})
2. Métricas agregadas del sistema (GET /api/v1/monitoring/metrics)

Estos endpoints permiten implementar un panel de benchmarking en tiempo real.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_async_session
from core.database.queries import get_ingest_status, get_metrics_aggregation
from datetime import datetime, timezone

router = APIRouter(prefix="/api/v1/monitoring", tags=["monitoring"])


@router.get("/ingest/{message_id}")
async def get_ingest_status_endpoint(
    message_id: str,
    session: AsyncSession = Depends(get_async_session)
):
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
        raise HTTPException(
            status_code=404,
            detail=f"Message ID '{message_id}' not found"
        )

    return status


@router.get("/metrics")
async def get_metrics_endpoint(
    period_hours: int = Query(24, ge=1, le=8760),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Obtiene métricas agregadas del sistema en un período.

    Query Parameters:
        period_hours: Horas atrás a analizar (1-8760, default 24)

    Returns: {
        "success_rate_percent": 96.5,
        "total_messages": 1250,
        "successful": 1200,
        "failed": 50,
        "period_hours": 24,
        "avg_latency_ms": 1585.42,
        "p95_latency_ms": 2100.0,
        "p99_latency_ms": 2800.0,
        "error_rate_by_source": {
            "catalunya": 2.5,
            "valencia": 4.2,
            "galicia": 3.1
        },
        "per_source_stats": {
            "catalunya": {
                "total": 500,
                "successful": 490,
                "failed": 10,
                "rate": 98.0
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


@router.get("/health-detailed")
async def get_health_detailed_endpoint(
    session: AsyncSession = Depends(get_async_session)
):
    """
    Obtiene información detallada de salud del sistema (debugging).

    Útil para diagnósticos y monitoreo interno.

    Returns: {
        "timestamp": "2026-03-20T12:00:00+00:00",
        "status": "healthy|degraded|unhealthy",
        "ingestion_pipeline": {
            "recent_messages_24h": 250,
            "success_rate_24h": 96.5,
            "avg_latency_ms": 1585.42
        },
        "database": {
            "status": "connected|disconnected"
        },
        "rabbitmq": {
            "status": "connected|disconnected"
            # queue_depths si está disponible
        }
    }
    """
    metrics = await get_metrics_aggregation(session, 24)

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "healthy" if metrics["success_rate_percent"] >= 90 else "degraded" if metrics["success_rate_percent"] >= 70 else "unhealthy",
        "ingestion_pipeline": {
            "recent_messages_24h": metrics.get("total_messages", 0),
            "success_rate_24h": metrics.get("success_rate_percent", 0),
            "avg_latency_ms": metrics.get("avg_latency_ms", 0),
            "p95_latency_ms": metrics.get("p95_latency_ms", 0),
        },
        "database": {
            "status": "connected"  # Si llegó aquí, BD está operativa
        },
        "metrics": metrics,
    }
