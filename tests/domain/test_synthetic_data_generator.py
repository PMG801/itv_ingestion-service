"""Tests for synthetic data generator."""

from __future__ import annotations

import pytest
import math

from domain.itv_stations.rules import ITVValidationRules, PROVINCE_COORDS_RANGE, PROVINCE_POSTAL_CODES
from domain.synthetic_data_generator import SyntheticDataGenerator, InvalidSyntheticDataGenerator


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


# ============================================================================
# Tests for InvalidSyntheticDataGenerator
# ============================================================================


def test_invalid_generator_creates_invalid_postal_code() -> None:
    """Test that invalid generator creates postal codes that don't match province."""
    payload = InvalidSyntheticDataGenerator.generate_invalid_stations(
        source="catalunya", count=10, error_types=["invalid_postal_code"]
    )

    stations = _extract_station_list(payload, "catalunya")
    assert len(stations) == 10

    for station in stations:
        postal_code = station["codi_postal"]
        province = station["provincia"]
        expected_prefix = PROVINCE_POSTAL_CODES.get(province.upper(), "28")
        # Should NOT start with the expected prefix for the province
        assert not postal_code.startswith(expected_prefix), f"Postal {postal_code} should not match province {province}"


def test_invalid_generator_creates_invalid_province() -> None:
    """Test that invalid generator creates non-existent provinces."""
    payload = InvalidSyntheticDataGenerator.generate_invalid_stations(
        source="valencia", count=10, error_types=["invalid_province"]
    )

    stations = _extract_station_list(payload, "valencia")
    assert len(stations) == 10

    for station in stations:
        province = station["provincia"]
        # Should not validate against Spanish provinces
        assert not ITVValidationRules.validate_province_spain(province)


def test_invalid_generator_creates_coordinates_outside_spain() -> None:
    """Test that invalid generator creates coordinates outside Spain."""
    payload = InvalidSyntheticDataGenerator.generate_invalid_stations(
        source="galicia", count=10, error_types=["coordinates_outside_spain"]
    )

    stations = _extract_station_list(payload, "galicia")
    assert len(stations) == 10

    for station in stations:
        latitude = station["lat"]
        longitude = station["lon"]
        # Should fail Spain coordinates validation
        assert not ITVValidationRules.validate_coordinates(latitude, longitude)


def test_invalid_generator_creates_invalid_emails() -> None:
    """Test that invalid generator creates malformed emails."""
    payload = InvalidSyntheticDataGenerator.generate_invalid_stations(
        source="catalunya", count=10, error_types=["invalid_email"]
    )

    stations = _extract_station_list(payload, "catalunya")
    assert len(stations) == 10

    for station in stations:
        email = station["email"]
        # Should fail email validation
        assert not ITVValidationRules.validate_email_simple(email)


def test_invalid_generator_creates_missing_contact_fields() -> None:
    """Test that invalid generator creates stations with missing contact/location fields."""
    payload = InvalidSyntheticDataGenerator.generate_invalid_stations(
        source="valencia", count=10, error_types=["missing_contact_fields"]
    )

    stations = _extract_station_list(payload, "valencia")
    assert len(stations) == 10

    for station in stations:
        # At least one of these should be None or empty
        phone = station["telefono"]
        email = station["correo"]
        address = station["direccion"]
        city = station["poblacion"]
        province = station["provincia"]
        postal = station["codigo_postal"]

        has_contact = phone or email
        has_location = address and city and province and postal

        # Should fail contact_minimum validation (missing contact OR location info)
        is_valid = has_contact and has_location
        assert not is_valid, "Should have missing contact or location fields"


def test_invalid_generator_respects_count_parameter() -> None:
    """Test that invalid generator respects count parameter."""
    for count in [1, 5, 10, 20]:
        payload = InvalidSyntheticDataGenerator.generate_invalid_stations(
            source="galicia", count=count, error_types=["invalid_postal_code"]
        )
        assert len(_extract_station_list(payload, "galicia")) == count


def test_invalid_generator_respects_error_types_filter() -> None:
    """Test that invalid generator only injects specified error types."""
    # Request only invalid_postal_code errors
    payload = InvalidSyntheticDataGenerator.generate_invalid_stations(
        source="catalunya", count=10, error_types=["invalid_postal_code"]
    )

    stations = _extract_station_list(payload, "catalunya")
    assert len(stations) == 10

    # All should have invalid postal codes
    for station in stations:
        postal_code = station["codi_postal"]
        province = station["provincia"]
        expected_prefix = PROVINCE_POSTAL_CODES.get(province.upper(), "28")
        assert not postal_code.startswith(expected_prefix)


def test_invalid_generator_works_with_all_sources() -> None:
    """Test that invalid generator works with all sources."""
    sources = ["catalunya", "valencia", "galicia"]

    for source in sources:
        payload = InvalidSyntheticDataGenerator.generate_invalid_stations(
            source=source, count=5, error_types=["invalid_province"]
        )
        stations = _extract_station_list(payload, source)
        assert len(stations) == 5


def test_invalid_generator_with_no_error_types_uses_random() -> None:
    """Test that invalid generator randomly selects error types when not specified."""
    # Call multiple times - should generate without error
    for _ in range(5):
        payload = InvalidSyntheticDataGenerator.generate_invalid_stations(
            source="valencia", count=10, error_types=None  # No specific types
        )
        stations = _extract_station_list(payload, "valencia")
        assert len(stations) == 10


def test_invalid_generator_raises_on_invalid_source() -> None:
    """Test that invalid generator raises on invalid source."""
    with pytest.raises(ValueError):
        InvalidSyntheticDataGenerator.generate_invalid_stations(
            source="invalid_source", count=5
        )


def test_invalid_generator_raises_on_invalid_error_types() -> None:
    """Test that invalid generator raises on invalid error types."""
    with pytest.raises(ValueError):
        InvalidSyntheticDataGenerator.generate_invalid_stations(
            source="catalunya", count=5, error_types=["invalid_error_type"]
        )


def test_invalid_generator_undersized_station_id() -> None:
    """Test that invalid generator creates undersized station IDs."""
    payload = InvalidSyntheticDataGenerator.generate_invalid_stations(
        source="galicia", count=10, error_types=["undersized_station_id"]
    )

    stations = _extract_station_list(payload, "galicia")
    assert len(stations) == 10

    for station in stations:
        station_id = station["id"]
        assert len(station_id) < 3, f"Station ID should be < 3 chars, got {station_id}"


def test_invalid_generator_oversized_name() -> None:
    """Test that invalid generator creates oversized names."""
    payload = InvalidSyntheticDataGenerator.generate_invalid_stations(
        source="catalunya", count=10, error_types=["oversized_name"]
    )

    stations = _extract_station_list(payload, "catalunya")
    assert len(stations) == 10

    for station in stations:
        name = station["nom"]
        assert len(name) > 200, f"Name should be > 200 chars, got {len(name)}"


def test_invalid_generator_malformed_coordinates() -> None:
    """Test that invalid generator creates malformed (NaN) coordinates."""
    payload = InvalidSyntheticDataGenerator.generate_invalid_stations(
        source="valencia", count=10, error_types=["malformed_coordinates"]
    )

    stations = _extract_station_list(payload, "valencia")
    assert len(stations) == 10

    for station in stations:
        latitude = station["latitud"]
        longitude = station["longitud"]
        # Should be NaN
        assert math.isnan(latitude), f"Latitude should be NaN, got {latitude}"
        assert math.isnan(longitude), f"Longitude should be NaN, got {longitude}"
