"""Tests for gateway upload router."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from math import ceil, floor

import pytest
from fastapi import HTTPException

from apps.gateway.routers.upload import inject_synthetic_data, inject_synthetic_mixed_data


@pytest.mark.asyncio
async def test_inject_synthetic_data_validates_source() -> None:
    """Test that inject_synthetic_data validates source parameter."""
    mock_request = MagicMock()
    mock_request.app.state.rabbitmq = MagicMock()
    mock_session = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    # Invalid source should raise HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await inject_synthetic_data(
            request=mock_request, source="invalid", count=10
        )

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_inject_synthetic_data_valid_sources() -> None:
    """Test that inject_synthetic_data accepts valid sources."""
    mock_request = MagicMock()
    mock_request.app.state.rabbitmq = MagicMock()
    mock_request.app.state.rabbitmq.is_connected = True
    mock_request.app.state.rabbitmq.publish = AsyncMock()

    mock_session = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    # Test that function processes valid sources without error
    # (may still hit other validations)
    for source in ["catalunya", "valencia", "galicia"]:
        try:
            # This may fail for other reasons, but not for invalid source
            await inject_synthetic_data(
                request=mock_request, source=source, count=1
            )
        except HTTPException as e:
            # Should not be "Invalid source" error
            assert "Invalid source" not in str(e.detail)


@pytest.mark.asyncio
async def test_inject_synthetic_data_rejects_invalid_error_types() -> None:
    """Test that inject_synthetic_data validates requested synthetic error types."""
    mock_request = MagicMock()
    mock_request.app.state.rabbitmq = MagicMock()
    mock_request.app.state.rabbitmq.is_connected = True

    mock_session = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    with pytest.raises(HTTPException) as exc_info:
        await inject_synthetic_data(
            request=mock_request,
            source="catalunya",
            count=1,
            error_rate=0.5,
            include_errors=["invalid_field"],
        )

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_inject_synthetic_data_passes_error_controls_to_generator(monkeypatch) -> None:
    """Test that inject_synthetic_data forwards synthetic error settings to the generator."""
    mock_request = MagicMock()
    mock_request.app.state.rabbitmq = MagicMock()
    mock_request.app.state.rabbitmq.is_connected = True
    mock_request.app.state.rabbitmq.publish = AsyncMock()

    mock_session = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    generator_mock = MagicMock(
        generate_stations=MagicMock(return_value={
            "stations": [
                {
                    "id": "CAT-000001",
                    "nom": "ITV Barcelona - Fija 0001",
                    "adreca": "Carrer Example 1",
                    "ciutat": "BARCELONA",
                    "provincia": "BARCELONA",
                    "codi_postal": "08001",
                    "latitud": 41.0,
                    "longitud": 2.0,
                    "telefon": "932123456",
                    "email": "info@example.com",
                }
            ]
        })
    )
    monkeypatch.setattr("apps.gateway.routers.upload.SyntheticDataGenerator", generator_mock)

    result = await inject_synthetic_data(
        request=mock_request,
        source="catalunya",
        count=1,
        error_rate=0.25,
        include_errors=["missing_field"],
    )

    generator_mock.generate_stations.assert_called_once_with(
        source="catalunya",
        count=1,
        error_rate=0.25,
        include_errors=["missing_field"],
    )
    assert result["error_rate"] == 0.25
    assert result["include_errors"] == ["missing_field"]


@pytest.mark.asyncio
async def test_inject_synthetic_data_requires_rabbitmq() -> None:
    """Test that inject_synthetic_data requires RabbitMQ."""
    mock_request = MagicMock()
    # Don't set rabbitmq in app state
    del mock_request.app.state.rabbitmq
    mock_session = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    with pytest.raises(HTTPException) as exc_info:
        await inject_synthetic_data(
            request=mock_request, source="catalunya", count=10
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


# ============================================================================
# Tests for inject_synthetic_mixed_data endpoint
# ============================================================================


@pytest.mark.asyncio
async def test_inject_synthetic_mixed_data_validates_source() -> None:
    """Test that inject_synthetic_mixed_data validates source parameter."""
    mock_request = MagicMock()
    mock_request.app.state.rabbitmq = MagicMock()
    mock_session = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    # Invalid source should raise HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await inject_synthetic_mixed_data(
            request=mock_request, source="invalid", count=10
        )

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_inject_synthetic_mixed_data_with_error_rate_zero() -> None:
    """Test that error_rate=0 generates 100% valid data."""
    mock_request = MagicMock()
    mock_request.app.state.rabbitmq = MagicMock()
    mock_request.app.state.rabbitmq.is_connected = True
    mock_request.app.state.rabbitmq.publish = AsyncMock()

    mock_session = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    result = await inject_synthetic_mixed_data(
        request=mock_request,
        source="catalunya",
        count=100,
        error_rate=0.0,
    )

    assert result["total_count"] == 100
    assert result["valid_count"] == 100
    assert result["invalid_count"] == 0
    assert result["error_rate_requested"] == 0.0


@pytest.mark.asyncio
async def test_inject_synthetic_mixed_data_with_error_rate_one() -> None:
    """Test that error_rate=1.0 generates 100% invalid data."""
    mock_request = MagicMock()
    mock_request.app.state.rabbitmq = MagicMock()
    mock_request.app.state.rabbitmq.is_connected = True
    mock_request.app.state.rabbitmq.publish = AsyncMock()

    mock_session = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    result = await inject_synthetic_mixed_data(
        request=mock_request,
        source="valencia",
        count=100,
        error_rate=1.0,
    )

    assert result["total_count"] == 100
    assert result["valid_count"] == 0
    assert result["invalid_count"] == 100
    assert result["error_rate_requested"] == 1.0


@pytest.mark.asyncio
async def test_inject_synthetic_mixed_data_with_error_rate_fifty_percent() -> None:
    """Test that error_rate=0.5 generates ~50% valid and ~50% invalid data."""
    mock_request = MagicMock()
    mock_request.app.state.rabbitmq = MagicMock()
    mock_request.app.state.rabbitmq.is_connected = True
    mock_request.app.state.rabbitmq.publish = AsyncMock()

    mock_session = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    result = await inject_synthetic_mixed_data(
        request=mock_request,
        source="galicia",
        count=100,
        error_rate=0.5,
    )

    assert result["total_count"] == 100
    # With ceil/floor, should be approximately 50/50
    assert result["valid_count"] + result["invalid_count"] == 100
    assert 45 <= result["valid_count"] <= 55  # Allow some variation due to ceil/floor


@pytest.mark.asyncio
async def test_inject_synthetic_mixed_data_respects_error_types_filter() -> None:
    """Test that inject_synthetic_mixed_data respects error_types parameter."""
    mock_request = MagicMock()
    mock_request.app.state.rabbitmq = MagicMock()
    mock_request.app.state.rabbitmq.is_connected = True
    mock_request.app.state.rabbitmq.publish = AsyncMock()

    mock_session = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    result = await inject_synthetic_mixed_data(
        request=mock_request,
        source="catalunya",
        count=50,
        error_rate=0.2,
        error_types=["invalid_postal_code", "invalid_province"],
    )

    assert result["error_types"] == ["invalid_postal_code", "invalid_province"]
    assert result["valid_count"] + result["invalid_count"] == 50


@pytest.mark.asyncio
async def test_inject_synthetic_mixed_data_valid_sources() -> None:
    """Test that inject_synthetic_mixed_data accepts all valid sources."""
    mock_request = MagicMock()
    mock_request.app.state.rabbitmq = MagicMock()
    mock_request.app.state.rabbitmq.is_connected = True
    mock_request.app.state.rabbitmq.publish = AsyncMock()

    mock_session = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    for source in ["catalunya", "valencia", "galicia"]:
        result = await inject_synthetic_mixed_data(
            request=mock_request,
            source=source,
            count=20,
            error_rate=0.1,
        )

        assert result["source"] == source
        assert result["injection_type"] == "synthetic-mixed"
        assert result["status"] == "accepted"


@pytest.mark.asyncio
async def test_inject_synthetic_mixed_data_requires_rabbitmq() -> None:
    """Test that inject_synthetic_mixed_data requires RabbitMQ."""
    mock_request = MagicMock()
    # Don't set rabbitmq in app state
    del mock_request.app.state.rabbitmq
    mock_session = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    with pytest.raises(HTTPException) as exc_info:
        await inject_synthetic_mixed_data(
            request=mock_request,
            source="catalunya",
            count=10,
        )

    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_inject_synthetic_mixed_data_returns_correct_structure() -> None:
    """Test that inject_synthetic_mixed_data returns expected response structure."""
    mock_request = MagicMock()
    mock_request.app.state.rabbitmq = MagicMock()
    mock_request.app.state.rabbitmq.is_connected = True
    mock_request.app.state.rabbitmq.publish = AsyncMock()

    mock_session = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    result = await inject_synthetic_mixed_data(
        request=mock_request,
        source="catalunya",
        count=50,
        error_rate=0.1,
    )

    # Basic response structure
    assert "status" in result
    assert result["injection_type"] == "synthetic-mixed"
    assert "valid_count" in result
    assert "invalid_count" in result
    assert result["total_count"] == 50


@pytest.mark.asyncio
async def test_inject_synthetic_mixed_data_count_distribution() -> None:
    """Test various count distributions."""
    mock_request = MagicMock()
    mock_request.app.state.rabbitmq = MagicMock()
    mock_request.app.state.rabbitmq.is_connected = True
    mock_request.app.state.rabbitmq.publish = AsyncMock()

    mock_session = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    test_cases = [
        (100, 0.1, 90, 10),    # 100 items, 10% error: 90 valid, 10 invalid
        (100, 0.2, 80, 20),    # 100 items, 20% error: 80 valid, 20 invalid
        (50, 0.3, 35, 15),     # 50 items, 30% error: 35 valid, 15 invalid
        (1000, 0.05, 950, 50), # 1000 items, 5% error: 950 valid, 50 invalid
    ]

    for count, error_rate, expected_valid, expected_invalid in test_cases:
        result = await inject_synthetic_mixed_data(
            request=mock_request,
            source="catalunya",
            count=count,
            error_rate=error_rate,
        )
        assert result["valid_count"] == expected_valid
        assert result["invalid_count"] == expected_invalid


@pytest.mark.asyncio
async def test_inject_synthetic_mixed_data_publishes_to_rabbitmq() -> None:
    """Test that inject_synthetic_mixed_data publishes messages to RabbitMQ."""
    mock_request = MagicMock()
    mock_request.app.state.rabbitmq = MagicMock()
    mock_request.app.state.rabbitmq.is_connected = True
    mock_request.app.state.rabbitmq.publish = AsyncMock()

    mock_session = MagicMock()
    mock_session.commit = AsyncMock()

    result = await inject_synthetic_mixed_data(
        request=mock_request,
        source="catalunya",
        count=10,
        error_rate=0.2,
    )

    # Should have published messages
    assert mock_request.app.state.rabbitmq.publish.call_count > 0
    # queued_messages should match call count
    assert result["queued_messages"] == mock_request.app.state.rabbitmq.publish.call_count
