from __future__ import annotations

from copy import deepcopy

import pytest

from domain.itv_stations.schemas import NormalizedStation


@pytest.fixture
def normalized_station_payload() -> dict[str, object]:
    return {
        "station_id": "CAT_BCN-001",
        "name": "  ITV   Barcelona   Nord  ",
        "address": "Carrer de la Indústria 123",
        "city": "Barcelona",
        "province": "Barcelona",
        "postal_code": "08025",
        "latitude": 41.3851,
        "longitude": 2.1734,
        "phone": "+34932123456",
        "email": "info@itvbarcelona.cat",
        "source_system": "catalunya",
        "raw_id": "BCN-001",
    }


@pytest.fixture
def normalized_station(normalized_station_payload: dict[str, object]) -> NormalizedStation:
    return NormalizedStation(**deepcopy(normalized_station_payload))
