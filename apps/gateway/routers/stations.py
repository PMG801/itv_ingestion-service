"""
Stations Router para lectura de estaciones desde PostgreSQL.
"""

from typing import Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_async_session
from domain.itv_stations.models import EstacionITV

router = APIRouter(tags=["stations"])


@router.get("/api/v1/stations/all")
@router.get("/api/estaciones")
async def get_all_stations(
    session: AsyncSession = Depends(get_async_session),
    limit: int = Query(5000, ge=1, le=20000),
) -> list[dict[str, Any]]:
    stmt = select(EstacionITV).order_by(EstacionITV.id.desc()).limit(limit)
    result = await session.execute(stmt)
    stations = result.scalars().all()

    response = []
    for station in stations:
        extra = station.datos_extra or {}
        response.append(
            {
                "id": str(station.id),
                "nombre": station.nombre,
                "direccion": station.direccion or "",
                "localidad": extra.get("city") or "",
                "codigo_postal": station.codigo_postal or "",
                "provincia": extra.get("province") or "",
                "tipo": extra.get("tipo") or "Fija",
                "latitud": station.latitud,
                "longitud": station.longitud,
            }
        )

    return response  # type: ignore[return-value]
