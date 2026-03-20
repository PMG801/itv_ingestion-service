"""
Stations Router para lectura de estaciones y provincias desde PostgreSQL.
"""

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
):
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

    return response


@router.get("/api/v1/stations/provinces")
@router.get("/api/provincias")
async def get_provinces(session: AsyncSession = Depends(get_async_session)):
    stmt = select(EstacionITV)
    result = await session.execute(stmt)
    stations = result.scalars().all()

    provinces: set[str] = set()
    for station in stations:
        extra = station.datos_extra or {}
        province = extra.get("province")
        if isinstance(province, str) and province.strip():
            provinces.add(province.strip())

    return [{"id": index + 1, "nombre": name} for index, name in enumerate(sorted(provinces))]
