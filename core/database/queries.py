"""
Query builders para métricas y trazabilidad de ingesta.

Este módulo proporciona funciones para consultar ingestion_log y estaciones
con el fin de calcular estadísticas, latencias y análisis de rechazos.

Todas las funciones son async y retornan datos estructurados (dicts o typed dicts).
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Any

from sqlalchemy import func, select, text, and_
from sqlalchemy.ext.asyncio import AsyncSession

from domain.itv_stations.models import IngestionLog


async def get_ingest_status(
    session: AsyncSession,
    message_id: str
) -> Optional[dict[str, Any]]:
    """
    Obtiene el estado completo de una ingesta específica.

    Query: SELECT * FROM ingestion_log WHERE message_id = ?
           + análisis de metadata.timing

    Args:
        session: AsyncSession de SQLAlchemy
        message_id: UUID único del mensaje

    Returns:
        Dict con status, timing breakdown, stations count, queue depths
        O None si no existe el message_id
    """
    stmt = select(IngestionLog).where(IngestionLog.message_id == message_id)
    result = await session.execute(stmt)
    log = result.scalar_one_or_none()

    if not log:
        return None

    metadata = log.metadata_json or {}
    timing = metadata.get("timing", {})

    # Calcular duraciones
    timing_breakdown = _calculate_timing_breakdown(timing)

    return {
        "message_id": log.message_id,
        "status": log.status,
        "source_system": log.source_system,
        "timing": timing_breakdown,
        "stations": metadata.get("stations_processed", {}),
        "rejection_summary": metadata.get("rejection_summary", {}),
        "injection_type": metadata.get("injection_type", "api"),
        "processed_at": log.processed_at.isoformat(),
    }


async def get_metrics_aggregation(
    session: AsyncSession,
    period_hours: int = 24
) -> dict[str, Any]:
    """
    Calcula métricas agregadas del sistema en un período.

    Queries:
    - COUNT(*) por status
    - AVG(metadata->'timing'->...) para latencias
    - PERCENTILE_CONT para p50, p95, p99
    - Análisis por source_system

    Args:
        session: AsyncSession de SQLAlchemy
        period_hours: Horas atrás a considerar (default 24)

    Returns:
        Dict con success_rate, latencias, rechazos, queue depths
    """
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=period_hours)

    # Query base: filtrar por período
    base_stmt = select(IngestionLog).where(
        IngestionLog.processed_at >= cutoff_time
    )
    result = await session.execute(base_stmt)
    logs = result.scalars().all()

    if not logs:
        return {
            "success_rate_percent": 0.0,
            "total_messages": 0,
            "period_hours": period_hours,
            "avg_latency_ms": 0,
            "p95_latency_ms": 0,
            "p99_latency_ms": 0,
            "error_rate_by_source": {},
            "per_source_stats": {},
            "queue_depths": {},
            "top_rejection_reasons": [],
        }

    # Calcular estadísticas
    total = len(logs)
    successful = sum(1 for log in logs if log.status == "success")
    failed = sum(1 for log in logs if log.status == "failed")
    success_rate = (successful / total * 100) if total > 0 else 0.0

    # Extraer latencias totales
    latencies = []
    error_counts_by_source = {}
    rejection_reasons_all = {}
    sources_stats = {}

    for log in logs:
        metadata = log.metadata_json or {}
        timing = metadata.get("timing", {})

        # Calcular total_duration_ms
        duration_ms = _calculate_total_duration_ms(timing)
        if duration_ms:
            latencies.append(duration_ms)

        # Por fuente
        source = log.source_system
        if source not in sources_stats:
            sources_stats[source] = {"total": 0, "successful": 0, "failed": 0}

        sources_stats[source]["total"] += 1
        if log.status == "success":
            sources_stats[source]["successful"] += 1
        else:
            sources_stats[source]["failed"] += 1
            error_counts_by_source[source] = error_counts_by_source.get(source, 0) + 1

        # Extraer razones de rechazo
        rejection_summary = metadata.get("rejection_summary", {})
        if rejection_summary:
            reasons = rejection_summary.get("rejection_reasons", {})
            for reason, count in reasons.items():
                rejection_reasons_all[reason] = rejection_reasons_all.get(reason, 0) + count

    # Calcular percentiles de latencia
    latencies_sorted = sorted(latencies)
    avg_latency_ms = sum(latencies) / len(latencies) if latencies else 0
    p95_latency_ms = _percentile(latencies_sorted, 0.95)
    p99_latency_ms = _percentile(latencies_sorted, 0.99)

    # Error rate por fuente
    error_rate_by_source = {
        source: (error_counts_by_source.get(source, 0) / sources_stats[source]["total"] * 100)
        if sources_stats[source]["total"] > 0
        else 0
        for source in sources_stats.keys()
    }

    # Per source stats con rate
    per_source_stats = {
        source: {
            "total": stats["total"],
            "successful": stats["successful"],
            "failed": stats["failed"],
            "rate": (stats["successful"] / stats["total"] * 100)
            if stats["total"] > 0
            else 0,
        }
        for source, stats in sources_stats.items()
    }

    # Top rejection reasons
    top_rejection_reasons = sorted(
        [
            {
                "reason": reason,
                "count": count,
                "percentage": (count / sum(rejection_reasons_all.values()) * 100)
                if rejection_reasons_all
                else 0,
            }
            for reason, count in rejection_reasons_all.items()
        ],
        key=lambda x: x["count"],
        reverse=True,
    )[:10]  # Top 10

    return {
        "success_rate_percent": round(success_rate, 2),
        "total_messages": total,
        "successful": successful,
        "failed": failed,
        "period_hours": period_hours,
        "avg_latency_ms": round(avg_latency_ms, 2),
        "p95_latency_ms": round(p95_latency_ms, 2),
        "p99_latency_ms": round(p99_latency_ms, 2),
        "error_rate_by_source": error_rate_by_source,
        "per_source_stats": per_source_stats,
        "queue_depths": {},  # Será completado por RabbitMQ API helper
        "top_rejection_reasons": top_rejection_reasons,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def get_rejection_details(
    session: AsyncSession,
    message_id: str
) -> Optional[dict[str, Any]]:
    """
    Obtiene detalles de rechazos para un mensaje específico.

    Args:
        session: AsyncSession
        message_id: UUID del mensaje

    Returns:
        Dict con rejection_summary desde metadata
    """
    stmt = select(IngestionLog).where(IngestionLog.message_id == message_id)
    result = await session.execute(stmt)
    log = result.scalar_one_or_none()

    if not log:
        return None

    metadata = log.metadata_json or {}
    return metadata.get("rejection_summary", {})


# ============================================================================
# Funciones Auxiliares Privadas
# ============================================================================

def _calculate_timing_breakdown(timing: dict[str, str]) -> dict[str, int]:
    """
    Calcula duración de cada etapa desde timestamps ISO-8601.

    Args:
        timing: Dict con gateway_ingested_at, normalizer_started_at, etc.

    Returns:
        Dict con *_duration_ms para cada etapa, y total_duration_ms
    """
    try:
        gateway_ingested = None
        normalizer_started = None
        normalizer_completed = None
        persister_started = None
        persister_completed = None

        if "gateway_ingested_at" in timing:
            gateway_ingested = datetime.fromisoformat(
                timing["gateway_ingested_at"].replace("Z", "+00:00")
            )
        if "normalizer_started_at" in timing:
            normalizer_started = datetime.fromisoformat(
                timing["normalizer_started_at"].replace("Z", "+00:00")
            )
        if "normalizer_completed_at" in timing:
            normalizer_completed = datetime.fromisoformat(
                timing["normalizer_completed_at"].replace("Z", "+00:00")
            )
        if "persister_started_at" in timing:
            persister_started = datetime.fromisoformat(
                timing["persister_started_at"].replace("Z", "+00:00")
            )
        if "persister_completed_at" in timing:
            persister_completed = datetime.fromisoformat(
                timing["persister_completed_at"].replace("Z", "+00:00")
            )

        breakdown = {}

        # Gateway latency: gateway_ingested -> normalizer_started
        if gateway_ingested and normalizer_started:
            breakdown["gateway_latency_ms"] = int(
                (normalizer_started - gateway_ingested).total_seconds() * 1000
            )

        # Normalizer duration: normalizer_started -> normalizer_completed
        if normalizer_started and normalizer_completed:
            breakdown["normalizer_duration_ms"] = int(
                (normalizer_completed - normalizer_started).total_seconds() * 1000
            )

        # Persister duration: persister_started -> persister_completed
        if persister_started and persister_completed:
            breakdown["persister_duration_ms"] = int(
                (persister_completed - persister_started).total_seconds() * 1000
            )

        # Total duration
        if gateway_ingested and persister_completed:
            breakdown["total_duration_ms"] = int(
                (persister_completed - gateway_ingested).total_seconds() * 1000
            )

        return breakdown

    except (ValueError, KeyError, AttributeError):
        # Si hay error parsing timestamps, retornar breakdown vacío
        return {}


def _calculate_total_duration_ms(timing: dict[str, str]) -> Optional[int]:
    """Calcula duración total desde timing dict."""
    try:
        breakdown = _calculate_timing_breakdown(timing)
        return breakdown.get("total_duration_ms")
    except Exception:
        return None


def _percentile(sorted_list: list[float], percentile: float) -> float:
    """
    Calcula percentil de una lista ordenada.

    Args:
        sorted_list: Lista ordenada de números
        percentile: Percentil a calcular (0.0 - 1.0)

    Returns:
        Valor del percentil
    """
    if not sorted_list:
        return 0.0

    index = percentile * (len(sorted_list) - 1)
    lower = int(index)
    upper = min(lower + 1, len(sorted_list) - 1)
    weight = index - lower

    if upper == lower:
        return float(sorted_list[lower])

    return sorted_list[lower] * (1 - weight) + sorted_list[upper] * weight
