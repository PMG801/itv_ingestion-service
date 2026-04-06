"""Tests for synthetic data generator."""

from __future__ import annotations

import pytest

from domain.itv_stations.rules import ITVValidationRules
from domain.synthetic_data_generator import SyntheticDataGenerator


def _extract_station_list(payload: dict[str, object], source: str) -> list[dict[str, object]]:
    key = "estaciones" if source == "valencia" else "stations"
    stations = payload[key]
    assert isinstance(stations, list)
    return stations


def test_synthetic_data_generator_generates_stations() -> None:
    """Test that SyntheticDataGenerator generates station data."""
    payload = SyntheticDataGenerator.generate_stations(
        source="catalunya", count=5, error_rate=0.0, include_errors=[]
    )

    assert isinstance(payload, dict)
    stations = _extract_station_list(payload, "catalunya")
    assert len(stations) == 5
    for station in stations:
        assert isinstance(station, dict)


def test_synthetic_data_generator_respects_count_parameter() -> None:
    """Test that generator respects count parameter."""
    for count in [1, 5, 10]:
        payload = SyntheticDataGenerator.generate_stations(
            source="catalunya", count=count, error_rate=0.0, include_errors=[]
        )
        assert len(_extract_station_list(payload, "catalunya")) == count


def test_synthetic_data_generator_generates_with_different_sources() -> None:
    """Test that generator works with different sources."""
    sources = ["catalunya", "valencia", "galicia"]

    for source in sources:
        payload = SyntheticDataGenerator.generate_stations(
            source=source, count=2, error_rate=0.0, include_errors=[]
        )
        stations = _extract_station_list(payload, source)
        assert len(stations) == 2
        assert all(isinstance(s, dict) for s in stations)


def test_synthetic_data_generator_with_error_rate_zero() -> None:
    """Test that error_rate=0 generates clean data."""
    payload = SyntheticDataGenerator.generate_stations(
        source="catalunya", count=5, error_rate=0.0, include_errors=[]
    )

    stations = _extract_station_list(payload, "catalunya")
    assert len(stations) == 5
    assert all(isinstance(s, dict) for s in stations)


def test_synthetic_data_generator_with_error_injection() -> None:
    """Test that generator supports error injection."""
    # Should not crash when requesting error injection
    payload = SyntheticDataGenerator.generate_stations(
        source="galicia", count=5, error_rate=0.1, include_errors=["invalid_coordinates"]
    )

    assert len(_extract_station_list(payload, "galicia")) == 5


def test_synthetic_data_generator_with_multiple_errors() -> None:
    """Test that multiple error types can be combined."""
    payload = SyntheticDataGenerator.generate_stations(
        source="galicia",
        count=3,
        error_rate=0.2,
        include_errors=["invalid_coordinates", "missing_field"],
    )

    assert len(_extract_station_list(payload, "galicia")) == 3


def test_synthetic_data_generator_creates_dict_structure() -> None:
    """Test that generated stations are dictionaries."""
    payload = SyntheticDataGenerator.generate_stations(
        source="catalunya", count=3, error_rate=0.0, include_errors=[]
    )

    stations = _extract_station_list(payload, "catalunya")
    for station in stations:
        assert isinstance(station, dict)
        # Should have at least some identifiable fields
        assert len(station) > 0


def test_synthetic_data_generator_galicia_matches_province_rules() -> None:
    """Test that Galicia synthetic stations match province-specific validation rules."""
    payload = SyntheticDataGenerator.generate_stations(
        source="galicia", count=20, error_rate=0.0, include_errors=[]
    )

    stations = payload["stations"]
    assert len(stations) == 20

    for station in stations:
        province = station["provincia"]
        latitude = station["lat"]
        longitude = station["lon"]
        postal_code = station["cp"]

        assert ITVValidationRules.validate_province_spain(province)
        assert ITVValidationRules.validate_coordinates_by_province(latitude, longitude, province)
        assert ITVValidationRules.validate_postal_code_by_province(postal_code, province)


def test_synthetic_data_generator_keeps_name_city_pairs_unique() -> None:
    """Test that clean synthetic batches do not create within-message duplicates."""
    payload = SyntheticDataGenerator.generate_stations(
        source="valencia", count=100, error_rate=0.0, include_errors=[]
    )

    stations = _extract_station_list(payload, "valencia")
    name_city_pairs = {(station["nombre"], station["poblacion"]) for station in stations}

    assert len(name_city_pairs) == len(stations)
