"""Mappers for transforming Pydantic schemas to SQLAlchemy ORM models."""

from collections.abc import Mapping
from datetime import datetime, timezone

from shapely.geometry import Point
from geoalchemy2.shape import from_shape  # pyright: ignore[reportUnknownVariableType]

from .schemas import NormalizedStation
from .models import EstacionITV


def normalized_station_to_orm(
    schema: NormalizedStation,
    datos_extra_adicionales: Mapping[str, object] | None = None,
) -> EstacionITV:
    """
    Convierte un NormalizedStation (Pydantic) a EstacionITV (ORM).

    Realiza las siguientes transformaciones:
    1. Mapeo directo de campos estructurados
    2. Construcción de geometría PostGIS desde latitud/longitud
    3. Población de datos_extra JSONB con información no mapeada

    Args:
        schema: Instancia de NormalizedStation (output del Normalizer)
        datos_extra_adicionales: Diccionario opcional con datos extra
            que no están en NormalizedStation pero quieres guardar

    Returns:
        EstacionITV: Instancia ORM lista para persistir

    Example:
        >>> from domain.itv_stations.schemas import NormalizedStation
        >>> normalized = NormalizedStation(
        ...     station_id="CAT_001",
        ...     name="Estación Barcelona Norte",
        ...     source_system="catalunya",
        ...     latitude=41.4,
        ...     longitude=2.2
        ... )
        >>> orm_instance = normalized_station_to_orm(normalized)
        >>> print(orm_instance.nombre)
        'Estación Barcelona Norte'
    """

    # ========================================================================
    # 1. Crear geometría PostGIS desde coordenadas
    # ========================================================================
    location = None
    if schema.latitude is not None and schema.longitude is not None:
        # Crear punto Shapely (longitud, latitud) - OJO: orden invertido
        shapely_point = Point(schema.longitude, schema.latitude)
        # Convertir a WKBElement de GeoAlchemy2 con SRID 4326 (WGS84)
        location = from_shape(shapely_point, srid=4326)

    # ========================================================================
    # 2. Construir datos_extra JSONB
    # ========================================================================
    # Guardamos campos que NO están mapeados en columnas dedicadas
    # En este caso, guardamos todo excepto los que ya tenemos en columnas
    datos_extra: dict[str, object] = {
        # Snapshot completo del objeto normalizado (para auditoría)
        "normalized_snapshot": schema.model_dump(mode="json"),
        # Timestamp de normalización original
        "normalized_at": schema.normalized_at.isoformat(),
    }

    # Añadir city y province si están presentes (no tenemos columnas para ellos)
    if schema.city:
        datos_extra["city"] = schema.city
    if schema.province:
        datos_extra["province"] = schema.province

    # Añadir raw_id para trazabilidad
    if schema.raw_id:
        datos_extra["raw_id"] = schema.raw_id

    # Merge con datos adicionales si se proporcionan
    if datos_extra_adicionales:
        datos_extra.update(datos_extra_adicionales)

    now = datetime.now(timezone.utc)

    # ========================================================================
    # 3. Construir instancia ORM
    # ========================================================================
    estacion = EstacionITV(
        # Identificación y origen
        fuente_origen=schema.source_system,
        id_en_fuente=schema.station_id,  # station_id es único por fuente
        # Datos principales
        nombre=schema.name,
        # Coordenadas
        latitud=schema.latitude,
        longitud=schema.longitude,
        location=location,
        # Contacto
        telefono=schema.phone,
        email=schema.email,
        # Dirección
        direccion=schema.address,
        codigo_postal=schema.postal_code,
        # Datos flexibles
        datos_extra=datos_extra,
        # Timestamps (fecha_creacion tendrá default, fecha_actualizacion por trigger)
        fecha_creacion=now,
        fecha_actualizacion=now,
    )

    return estacion


def extract_datos_no_mapeados(schema: NormalizedStation) -> dict[str, object]:
    """
    Extrae campos de NormalizedStation que NO tienen columna dedicada.

    Útil si quieres separar claramente qué va a datos_extra.

    Args:
        schema: Instancia de NormalizedStation

    Returns:
        dict: Campos no mapeados en estructura de BD
    """
    return {
        "city": schema.city,
        "province": schema.province,
        "raw_id": schema.raw_id,
        "normalized_at": schema.normalized_at.isoformat(),
    }
