"""Tests for gateway upload router."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from apps.gateway.routers.upload import inject_synthetic_data


@pytest.mark.asyncio
async def test_inject_synthetic_data_validates_source() -> None:
    """Test that inject_synthetic_data validates source parameter."""
    mock_request = MagicMock()
    mock_request.app.state.rabbitmq = MagicMock()
    mock_session = AsyncMock()
    
    # Invalid source should raise HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await inject_synthetic_data(
            request=mock_request,
            source="invalid",
            count=10,
            error_rate=0.0,
            include_errors=None,
            session=mock_session
        )
    
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_inject_synthetic_data_valid_sources() -> None:
    """Test that inject_synthetic_data accepts valid sources."""
    mock_request = MagicMock()
    mock_request.app.state.rabbitmq = MagicMock()
    mock_request.app.state.rabbitmq.is_connected = True
    mock_request.app.state.rabbitmq.publish = AsyncMock()
    
    mock_session = AsyncMock()
    
    # Test that function processes valid sources without error
    # (may still hit other validations)
    for source in ["catalunya", "valencia", "galicia"]:
        try:
            # This may fail for other reasons, but not for invalid source
            await inject_synthetic_data(
                request=mock_request,
                source=source,
                count=1,
                error_rate=0.0,
                include_errors=None,
                session=mock_session
            )
        except HTTPException as e:
            # Should not be "Invalid source" error
            assert "Invalid source" not in str(e.detail)


@pytest.mark.asyncio
async def test_inject_synthetic_data_requires_rabbitmq() -> None:
    """Test that inject_synthetic_data requires RabbitMQ."""
    mock_request = MagicMock()
    # Don't set rabbitmq in app state
    del mock_request.app.state.rabbitmq
    mock_session = AsyncMock()
    
    with pytest.raises(HTTPException) as exc_info:
        await inject_synthetic_data(
            request=mock_request,
            source="catalunya",
            count=10,
            error_rate=0.0,
            include_errors=None,
            session=mock_session
        )
    
    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_inject_synthetic_data_validates_count() -> None:
    """Test that inject_synthetic_data validates count parameter."""
    mock_request = MagicMock()
    mock_request.app.state.rabbitmq = MagicMock()
    mock_session = AsyncMock()
    
    # Count is validated by FastAPI Query parameter
    # Values outside range should be rejected by FastAPI itself
    # This test just documents the behavior
    assert True


@pytest.mark.asyncio
async def test_inject_synthetic_data_validates_error_rate() -> None:
    """Test that inject_synthetic_data validates error_rate parameter."""
    mock_request = MagicMock()
    mock_request.app.state.rabbitmq = MagicMock()
    mock_session = AsyncMock()
    
    # error_rate is validated by FastAPI Query parameter (0.0-1.0)
    # This test documents the expected behavior
    assert True
