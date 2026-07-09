"""
Query builders para métricas y trazabilidad de ingesta.

Este módulo proporciona funciones para consultar ingestion_log y estaciones
con el fin de calcular estadísticas, latencias y análisis de rechazos.

Todas las funciones son async y retornan datos estructurados (dicts o typed dicts).
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from domain.itv_stations.models import IngestionLog, LLMMappingRule


async def get_ingest_status(session: AsyncSession, message_id: str) -> Optional[dict[str, Any]]:
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


async def get_metrics_aggregation(session: AsyncSession, period_hours: int = 24) -> dict[str, Any]:
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
        Dict con volumen, latencias, rechazos y estadísticas por fuente
    """
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=period_hours)

    # Query base: filtrar por período
    base_stmt = select(IngestionLog).where(IngestionLog.processed_at >= cutoff_time)
    result = await session.execute(base_stmt)
    logs = result.scalars().all()

    if not logs:
        return {
            "total_messages": 0,
            "successful": 0,
            "failed": 0,
            "period_hours": period_hours,
            "avg_latency_ms": 0,
            "p95_latency_ms": 0,
            "p99_latency_ms": 0,
            "per_source_stats": {},
            "queue_depths": {},
            "top_rejection_reasons": [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # Calcular estadísticas
    total = len(logs)
    successful = sum(1 for log in logs if log.status == "success")
    failed = sum(1 for log in logs if log.status == "failed")
    # Extraer latencias totales
    latencies = []
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

    # Per source stats
    per_source_stats = {  # type: ignore[assignment]
        source: {
            "total": stats["total"],
            "successful": stats["successful"],
            "failed": stats["failed"],
        }
        for source, stats in sources_stats.items()
    }

    # Top rejection reasons
    top_rejection_reasons = sorted(  # type: ignore[arg-type]
        [
            {
                "reason": reason,  # type: ignore[assignment]
                "count": count,  # type: ignore[assignment]
                "percentage": (
                    (count / sum(rejection_reasons_all.values()) * 100)  # type: ignore[operator]
                    if rejection_reasons_all
                    else 0
                ),
            }
            for reason, count in rejection_reasons_all.items()  # type: ignore[attr-defined]
        ],
        key=lambda x: x["count"],
        reverse=True,
    )[
        :10
    ]  # Top 10

    return {  # type: ignore[return-value]
        "total_messages": total,
        "successful": successful,
        "failed": failed,
        "period_hours": period_hours,
        "avg_latency_ms": round(avg_latency_ms, 2),
        "p95_latency_ms": round(p95_latency_ms, 2),
        "p99_latency_ms": round(p99_latency_ms, 2),
        "per_source_stats": per_source_stats,
        "queue_depths": {},  # Será completado por RabbitMQ API helper
        "top_rejection_reasons": top_rejection_reasons,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def get_rejection_details(session: AsyncSession, message_id: str) -> Optional[dict[str, Any]]:
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


# ============================================================================
# LLM Mapping Rules: CRUD operations for learned mapping rules per source type
# ============================================================================


async def get_active_llm_mapping_rule(
    session: AsyncSession, source_system: str, province_type: str
) -> Optional[dict[str, Any]]:
    """
    Obtiene la regla activa de mapeo LLM para un tipo de provincia/fuente.

    Solo retorna reglas activas (is_active=true). Si no existe regla activa,
    retorna None y el transformador debe generar una nueva mediante LLM.

    Args:
        session: AsyncSession de SQLAlchemy
        source_system: Sistema fuente (catalunya, valencia, galicia)
        province_type: Tipo de provincia que determina el patrón de estructura

    Returns:
        Dict con field_mapping y metadatos, o None si no existe regla activa
    """
    stmt = select(LLMMappingRule).where(
        (LLMMappingRule.source_system == source_system)
        & (LLMMappingRule.province_type == province_type)
        & (LLMMappingRule.is_active == True)
    )
    result = await session.execute(stmt)
    rule = result.scalar_one_or_none()

    if not rule:
        return None

    return {
        "id": rule.id,
        "source_system": rule.source_system,
        "province_type": rule.province_type,
        "field_mapping": rule.field_mapping,
        "llm_model": rule.llm_model,
        "llm_prompt_version": rule.llm_prompt_version,
        "confidence_score": rule.confidence_score,
        "sample_schema_signature": rule.sample_schema_signature,
        "generated_at": rule.generated_at.isoformat(),
        "updated_at": rule.updated_at.isoformat(),
    }


async def create_llm_mapping_rule(
    session: AsyncSession,
    source_system: str,
    province_type: str,
    field_mapping: dict[str, Any],
    llm_model: str,
    llm_prompt_version: str = "1.0",
    confidence_score: float = 0.95,
    sample_schema_signature: Optional[str] = None,
) -> LLMMappingRule:
    """
    Crea una nueva regla activa de mapeo LLM, desactivando la anterior si existe.

    Este flujo sigue la estrategia "una activa": se desactiva la regla anterior
    y se crea la nueva activa. El histórico se mantiene para auditoría.

    Args:
        session: AsyncSession de SQLAlchemy
        source_system: Sistema fuente
        province_type: Tipo de provincia
        field_mapping: Mapeo de campos descubierto por LLM
        llm_model: Nombre del modelo LLM usado
        llm_prompt_version: Versión del prompt usado
        confidence_score: Puntuación de confianza (0-1)
        sample_schema_signature: Firma del esquema del ejemplo usado

    Returns:
        La nueva regla LLMMappingRule creada y persistida
    """
    # Desactivar regla anterior si existe
    await deactivate_llm_mapping_rule_by_key(session, source_system, province_type)

    # Crear nueva regla activa
    new_rule = LLMMappingRule(
        source_system=source_system,
        province_type=province_type,
        field_mapping=field_mapping,
        llm_model=llm_model,
        llm_prompt_version=llm_prompt_version,
        confidence_score=confidence_score,
        sample_schema_signature=sample_schema_signature,
        is_active=True,
        generated_at=datetime.now(timezone.utc),
    )
    session.add(new_rule)
    await session.flush()
    return new_rule


async def deactivate_llm_mapping_rule_by_key(
    session: AsyncSession, source_system: str, province_type: str
) -> int:
    """
    Desactiva todas las reglas activas para una clave (source_system, province_type).

    Usado antes de crear una nueva regla activa para mantener la invariante
    de "una sola regla activa por clave".

    Args:
        session: AsyncSession de SQLAlchemy
        source_system: Sistema fuente
        province_type: Tipo de provincia

    Returns:
        Número de reglas desactivadas
    """
    stmt = (
        update(LLMMappingRule)
        .where(
            (LLMMappingRule.source_system == source_system)
            & (LLMMappingRule.province_type == province_type)
            & (LLMMappingRule.is_active == True)
        )
        .values(is_active=False)
    )
    result = await session.execute(stmt)
    await session.flush()
    return result.rowcount  # type: ignore[no-any-return]


async def list_llm_mapping_rules(
    session: AsyncSession, source_system: Optional[str] = None, include_inactive: bool = False
) -> list[dict[str, Any]]:
    """
    Lista todas las reglas de mapeo LLM (activas o todas según filtro).

    Args:
        session: AsyncSession de SQLAlchemy
        source_system: Filtrar por sistema fuente (opcional)
        include_inactive: Si False, solo retorna reglas activas

    Returns:
        Lista de dicts con metadatos de reglas
    """
    where_clauses = []
    if source_system:
        where_clauses.append(LLMMappingRule.source_system == source_system)
    if not include_inactive:
        where_clauses.append(LLMMappingRule.is_active == True)

    stmt = select(LLMMappingRule)
    for clause in where_clauses:
        stmt = stmt.where(clause)

    result = await session.execute(stmt)
    rules = result.scalars().all()

    return [
        {
            "id": rule.id,
            "source_system": rule.source_system,
            "province_type": rule.province_type,
            "field_mapping": rule.field_mapping,
            "llm_model": rule.llm_model,
            "confidence_score": rule.confidence_score,
            "is_active": rule.is_active,
            "generated_at": rule.generated_at.isoformat(),
        }
        for rule in rules
    ]
