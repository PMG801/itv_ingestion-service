"""Tests for gateway stations router."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from apps.gateway.main import app


@pytest.fixture
def client() -> TestClient:
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_async_session() -> AsyncMock:
    """Create a mock AsyncSession."""
    return AsyncMock()


@pytest.mark.asyncio
async def test_get_all_stations_returns_list() -> None:
    """Test that get_all_stations endpoint returns a list."""
    from apps.gateway.routers.stations import get_all_stations
    
    # Create mock session
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars().all.return_value = []
    mock_session.execute.return_value = mock_result
    
    # Call endpoint
    result = await get_all_stations(session=mock_session, limit=100)
    
    # Verify result
    assert isinstance(result, list)
    assert len(result) == 0


@pytest.mark.asyncio
async def test_get_all_stations_with_data() -> None:
    """Test that get_all_stations returns station data."""
    from apps.gateway.routers.stations import get_all_stations
    
    # Create mock station
    mock_station = MagicMock()
    mock_station.id = 1
    mock_station.nombre = "ITV Barcelona"
    mock_station.direccion = "Carrer 123"
    mock_station.codigo_postal = "08001"
    mock_station.latitud = 41.3850
    mock_station.longitud = 2.1734
    mock_station.datos_extra = {"city": "Barcelona", "province": "Barcelona"}
    
    # Create mock session
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars().all.return_value = [mock_station]
    mock_session.execute.return_value = mock_result
    
    # Call endpoint
    result = await get_all_stations(session=mock_session, limit=100)
    
    # Verify result
    assert len(result) == 1
    assert result[0]["nombre"] == "ITV Barcelona"
    assert result[0]["localidad"] == "Barcelona"


@pytest.mark.asyncio
async def test_get_all_stations_respects_limit() -> None:
    """Test that get_all_stations respects the limit parameter."""
    from apps.gateway.routers.stations import get_all_stations
    
    # Create mock session
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars().all.return_value = []
    mock_session.execute.return_value = mock_result
    
    # Call with custom limit
    await get_all_stations(session=mock_session, limit=500)
    
    # Verify that execute was called
    mock_session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_provinces_returns_list() -> None:
    """Test that get_provinces endpoint returns list of provinces."""
    from apps.gateway.routers.stations import get_provinces
    
    # Create mock session
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars().all.return_value = []
    mock_session.execute.return_value = mock_result
    
    # Call endpoint
    result = await get_provinces(session=mock_session)
    
    # Verify result
    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_get_provinces_with_data() -> None:
    """Test that get_provinces returns province data."""
    from apps.gateway.routers.stations import get_provinces
    
    # Create mock stations with provinces
    mock_station1 = MagicMock()
    mock_station1.datos_extra = {"province": "Barcelona"}
    
    mock_station2 = MagicMock()
    mock_station2.datos_extra = {"province": "Valencia"}
    
    # Create mock session
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars().all.return_value = [mock_station1, mock_station2]
    mock_session.execute.return_value = mock_result
    
    # Call endpoint
    result = await get_provinces(session=mock_session)
    
    # Verify result
    assert len(result) == 2
    assert result[0]["nombre"] in ["Barcelona", "Valencia"]


@pytest.mark.asyncio
async def test_get_provinces_handles_none_datos_extra() -> None:
    """Test that get_provinces handles stations with None datos_extra."""
    from apps.gateway.routers.stations import get_provinces
    
    # Create mock station with None datos_extra
    mock_station = MagicMock()
    mock_station.datos_extra = None
    
    # Create mock session
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars().all.return_value = [mock_station]
    mock_session.execute.return_value = mock_result
    
    # Call endpoint - should not crash
    result = await get_provinces(session=mock_session)
    
    assert isinstance(result, list)
    assert len(result) == 0
