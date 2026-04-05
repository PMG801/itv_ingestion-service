"""Tests for ORM models."""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from geoalchemy2 import Geometry

from domain.itv_stations.models import EstacionITV, IngestionLog


def test_estacion_itv_model_initialization() -> None:
    """Test that EstacionITV model can be initialized."""
    station = EstacionITV()

    # Check that model has expected attributes
    assert hasattr(station, "id")
    assert hasattr(station, "nombre")
    assert hasattr(station, "direccion")
    assert hasattr(station, "codigo_postal")
    assert hasattr(station, "latitud")
    assert hasattr(station, "longitud")
    assert hasattr(station, "datos_extra")


def test_estacion_itv_stores_geometry_data() -> None:
    """Test that EstacionITV stores geometry data correctly."""
    station = EstacionITV()
    station.nombre = "ITV Barcelona"
    station.latitud = 41.3851
    station.longitud = 2.1734

    assert station.nombre == "ITV Barcelona"
    assert station.latitud == 41.3851
    assert station.longitud == 2.1734


def test_estacion_itv_stores_extra_data() -> None:
    """Test that EstacionITV stores extra data as JSON."""
    station = EstacionITV()
    station.datos_extra = {
        "city": "Barcelona",
        "province": "Barcelona",
        "tipo": "Fija",
        "phone": "+34932123456",
    }

    assert station.datos_extra["city"] == "Barcelona"
    assert station.datos_extra["province"] == "Barcelona"
    assert station.datos_extra["tipo"] == "Fija"


def test_ingestion_log_model_initialization() -> None:
    """Test that IngestionLog model can be initialized."""
    log = IngestionLog()

    # Check that model has expected attributes
    assert hasattr(log, "id")
    assert hasattr(log, "message_id")
    assert hasattr(log, "status")
    assert hasattr(log, "source_system")
    assert hasattr(log, "metadata_json")
    assert hasattr(log, "processed_at")


def test_ingestion_log_stores_metadata() -> None:
    """Test that IngestionLog stores metadata as JSON."""
    log = IngestionLog()
    log.message_id = "test-123"
    log.status = "success"
    log.source_system = "catalunya"
    log.metadata_json = {
        "timing": {
            "gateway_latency_ms": 50,
            "normalizer_duration_ms": 1200,
        },
        "stations_processed": {
            "successful": 100,
            "failed": 5,
        },
        "injection_type": "api",
    }

    assert log.message_id == "test-123"
    assert log.metadata_json["stations_processed"]["successful"] == 100
    assert log.metadata_json["timing"]["gateway_latency_ms"] == 50


def test_ingestion_log_tracks_processing_status() -> None:
    """Test that IngestionLog correctly tracks various statuses."""
    valid_statuses = ["processing", "success", "failed", "partial"]

    for status in valid_statuses:
        log = IngestionLog()
        log.status = status
        assert log.status == status


def test_ingestion_log_timestamp_is_recorded() -> None:
    """Test that IngestionLog records processing timestamp."""
    log = IngestionLog()
    now = datetime.now(timezone.utc)
    log.processed_at = now

    assert log.processed_at is not None
    assert isinstance(log.processed_at, datetime)


def test_estacion_itv_handles_null_coordinates() -> None:
    """Test that EstacionITV handles null/None coordinates gracefully."""
    station = EstacionITV()
    station.latitud = None
    station.longitud = None

    assert station.latitud is None
    assert station.longitud is None


def test_estacion_itv_handles_missing_extra_data() -> None:
    """Test that EstacionITV handles missing extra data fields."""
    station = EstacionITV()
    station.datos_extra = None

    # Should support None for datos_extra
    assert station.datos_extra is None


def test_ingestion_log_source_system_can_be_set() -> None:
    """Test that IngestionLog source_system can be set to different values."""
    sources = ["catalunya", "valencia", "galicia"]

    for source in sources:
        log = IngestionLog()
        log.source_system = source
        assert log.source_system == source


@pytest.mark.parametrize(
    "lat,lon",
    [
        (41.3851, 2.1734),  # Barcelona
        (39.4699, -0.3763),  # Valencia
        (42.5980, 1.6445),  # Girona
    ],
)
def test_estacion_itv_stores_valid_coordinates(lat: float, lon: float) -> None:
    """Test that EstacionITV stores valid coordinate pairs."""
    station = EstacionITV()
    station.latitud = lat
    station.longitud = lon

    assert station.latitud == lat
    assert station.longitud == lon
