"""Tests for synthetic data generator."""

from __future__ import annotations

import pytest

from domain.synthetic_data_generator import SyntheticDataGenerator


def test_synthetic_data_generator_generates_stations() -> None:
    """Test that SyntheticDataGenerator generates station data."""
    stations = SyntheticDataGenerator.generate_stations(
        source="catalunya",
        count=5,
        error_rate=0.0,
        include_errors=[]
    )
    
    assert isinstance(stations, list)
    assert len(stations) == 5
    # Each element should be dict-like
    for station in stations:
        assert isinstance(station, dict)


def test_synthetic_data_generator_respects_count_parameter() -> None:
    """Test that generator respects count parameter."""
    for count in [1, 5, 10]:
        stations = SyntheticDataGenerator.generate_stations(
            source="catalunya",
            count=count,
            error_rate=0.0,
            include_errors=[]
        )
        assert len(stations) == count


def test_synthetic_data_generator_generates_with_different_sources() -> None:
    """Test that generator works with different sources."""
    sources = ["catalunya", "valencia", "galicia"]
    
    for source in sources:
        stations = SyntheticDataGenerator.generate_stations(
            source=source,
            count=2,
            error_rate=0.0,
            include_errors=[]
        )
        assert len(stations) == 2
        assert all(isinstance(s, dict) for s in stations)


def test_synthetic_data_generator_with_error_rate_zero() -> None:
    """Test that error_rate=0 generates clean data."""
    stations = SyntheticDataGenerator.generate_stations(
        source="catalunya",
        count=5,
        error_rate=0.0,
        include_errors=[]
    )
    
    assert len(stations) == 5
    assert all(isinstance(s, dict) for s in stations)


def test_synthetic_data_generator_with_error_injection() -> None:
    """Test that generator supports error injection."""
    # Should not crash when requesting error injection
    stations = SyntheticDataGenerator.generate_stations(
        source="galicia",
        count=5,
        error_rate=0.1,
        include_errors=["invalid_coordinates"]
    )
    
    assert len(stations) == 5


def test_synthetic_data_generator_with_multiple_errors() -> None:
    """Test that multiple error types can be combined."""
    stations = SyntheticDataGenerator.generate_stations(
        source="galicia",
        count=3,
        error_rate=0.2,
        include_errors=["invalid_coordinates", "missing_field"]
    )
    
    assert len(stations) == 3


def test_synthetic_data_generator_creates_dict_structure() -> None:
    """Test that generated stations are dictionaries."""
    stations = SyntheticDataGenerator.generate_stations(
        source="catalunya",
        count=3,
        error_rate=0.0,
        include_errors=[]
    )
    
    for station in stations:
        assert isinstance(station, dict)
        # Should have at least some identifiable fields
        assert len(station) > 0
