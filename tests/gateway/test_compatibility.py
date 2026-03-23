"""Tests for gateway compatibility router."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.gateway.routers.compatibility import (
    load_data,
    _message_id_cache,
)


@pytest.fixture(autouse=True)
def clean_cache() -> None:
    """Clean message cache before each test."""
    _message_id_cache.clear()
    yield
    _message_id_cache.clear()


@pytest.mark.asyncio
async def test_load_data_requires_fuente() -> None:
    """Test that load_data requires 'fuente' field."""
    from fastapi import HTTPException
    
    mock_session = AsyncMock()
    
    # Call without fuente
    with pytest.raises(HTTPException) as exc_info:
        await load_data(payload={}, session=mock_session)
    
    assert exc_info.value.status_code == 400
    assert "fuente" in str(exc_info.value.detail).lower()


@pytest.mark.asyncio
async def test_load_data_validates_source_code() -> None:
    """Test that load_data validates source codes."""
    from fastapi import HTTPException
    
    mock_session = AsyncMock()
    
    # Call with invalid source
    with pytest.raises(HTTPException) as exc_info:
        await load_data(payload={"fuente": "INVALID"}, session=mock_session)
    
    assert exc_info.value.status_code == 400
    assert "inválida" in str(exc_info.value.detail).lower()

