from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

from domain.itv_stations.rules import ITVValidationRules
from domain.itv_stations.schemas import NormalizedStation


def test_normalized_station_applies_basic_normalization(
    normalized_station_payload: dict[str, object],
) -> None:
    station = NormalizedStation(**deepcopy(normalized_station_payload))

    assert station.name == "ITV Barcelona Nord"
    assert station.city == "BARCELONA"
    assert station.province == "BARCELONA"
    assert station.source_system == "catalunya"


def test_normalized_station_rejects_coordinates_outside_spain(
    normalized_station_payload: dict[str, object],
) -> None:
    invalid_payload = deepcopy(normalized_station_payload)
    invalid_payload["latitude"] = 55.0

    with pytest.raises(ValidationError):
        NormalizedStation(**invalid_payload)


def test_validate_coordinates_accepts_values_within_spain() -> None:
    assert ITVValidationRules.validate_coordinates(41.3851, 2.1734) is True


@pytest.mark.parametrize(
    ("latitude", "longitude"),
    [
        (None, 2.1734),
        (41.3851, None),
        (45.0, 2.1734),
        (41.3851, -12.0),
    ],
)
def test_validate_coordinates_rejects_invalid_values(
    latitude: float | None,
    longitude: float | None,
) -> None:
    assert ITVValidationRules.validate_coordinates(latitude, longitude) is False