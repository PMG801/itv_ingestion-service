from __future__ import annotations

from copy import deepcopy

from domain.itv_stations.mappers import extract_datos_no_mapeados, normalized_station_to_orm
from domain.itv_stations.schemas import NormalizedStation


def test_normalized_station_to_orm_maps_core_fields_and_geometry(
    normalized_station: NormalizedStation,
) -> None:
    orm_station = normalized_station_to_orm(
        normalized_station,
        datos_extra_adicionales={"region_code": "CAT"},
    )

    assert orm_station.fuente_origen == "catalunya"
    assert orm_station.id_en_fuente == "CAT_BCN-001"
    assert orm_station.nombre == "ITV Barcelona Nord"
    assert orm_station.latitud == 41.3851
    assert orm_station.longitud == 2.1734
    assert orm_station.location is not None
    assert orm_station.location.srid == 4326
    assert orm_station.telefono == "+34932123456"
    assert orm_station.codigo_postal == "08025"
    assert orm_station.datos_extra["city"] == "BARCELONA"
    assert orm_station.datos_extra["province"] == "BARCELONA"
    assert orm_station.datos_extra["raw_id"] == "BCN-001"
    assert orm_station.datos_extra["region_code"] == "CAT"
    assert orm_station.datos_extra["normalized_snapshot"]["station_id"] == "CAT_BCN-001"


def test_normalized_station_to_orm_skips_geometry_without_coordinates(
    normalized_station_payload: dict[str, object],
) -> None:
    payload = deepcopy(normalized_station_payload)
    payload["latitude"] = None
    payload["longitude"] = None
    station = NormalizedStation(**payload)

    orm_station = normalized_station_to_orm(station)

    assert orm_station.location is None
    assert orm_station.latitud is None
    assert orm_station.longitud is None


def test_extract_datos_no_mapeados_returns_traceability_fields(
    normalized_station: NormalizedStation,
) -> None:
    extra = extract_datos_no_mapeados(normalized_station)

    assert extra["city"] == "BARCELONA"
    assert extra["province"] == "BARCELONA"
    assert extra["raw_id"] == "BCN-001"
    assert extra["normalized_at"].startswith(str(normalized_station.normalized_at.year))