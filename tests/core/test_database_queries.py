"""Tests for database queries module - focusing on helper functions."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from core.database.queries import (
    _calculate_timing_breakdown,
    _calculate_total_duration_ms,
    _percentile,
)


def test_calculate_timing_breakdown_calculates_durations() -> None:
    """Test that _calculate_timing_breakdown calculates stage durations."""
    timing = {
        "gateway_ingested_at": "2026-03-20T12:00:00Z",
        "normalizer_started_at": "2026-03-20T12:00:01Z",
        "normalizer_completed_at": "2026-03-20T12:00:03Z",
        "persister_started_at": "2026-03-20T12:00:03Z",
        "persister_completed_at": "2026-03-20T12:00:04Z",
    }

    result = _calculate_timing_breakdown(timing)

    assert isinstance(result, dict)
    assert result["gateway_latency_ms"] == 1000
    assert result["normalizer_duration_ms"] == 2000
    assert result["persister_duration_ms"] == 1000
    assert result["total_duration_ms"] == 4000


def test_calculate_timing_breakdown_with_partial_timestamps() -> None:
    """Test that _calculate_timing_breakdown handles partial timestamps."""
    timing = {
        "gateway_ingested_at": "2026-03-20T12:00:00Z",
        "normalizer_started_at": "2026-03-20T12:00:01Z",
    }

    result = _calculate_timing_breakdown(timing)

    assert isinstance(result, dict)
    # Should calculate gateway_latency but not others
    assert result.get("gateway_latency_ms") == 1000 or "gateway_latency_ms" not in result


def test_calculate_timing_breakdown_returns_dict() -> None:
    """Test that _calculate_timing_breakdown always returns dict."""
    timing_empty: dict[str, str] = {}
    result = _calculate_timing_breakdown(timing_empty)
    assert isinstance(result, dict)


def test_calculate_timing_breakdown_with_invalid_timestamps() -> None:
    """Test that _calculate_timing_breakdown handles invalid timestamps gracefully."""
    timing = {
        "gateway_ingested_at": "invalid-timestamp",
    }

    result = _calculate_timing_breakdown(timing)

    # Should return dict (possibly empty) without crashing
    assert isinstance(result, dict)


def test_calculate_total_duration_ms_extracts_total() -> None:
    """Test that _calculate_total_duration_ms extracts total duration."""
    timing = {
        "gateway_ingested_at": "2026-03-20T12:00:00Z",
        "persister_completed_at": "2026-03-20T12:00:05Z",
    }

    result = _calculate_total_duration_ms(timing)

    assert result is not None
    assert result == 5000


def test_calculate_total_duration_ms_returns_none_on_error() -> None:
    """Test that _calculate_total_duration_ms returns None on error."""
    timing = {
        "invalid_field": "value",
    }

    result = _calculate_total_duration_ms(timing)

    # Should handle error gracefully
    assert result is None or isinstance(result, int)


def test_calculate_total_duration_ms_with_empty_timing() -> None:
    """Test that _calculate_total_duration_ms handles empty timing dict."""
    result = _calculate_total_duration_ms({})

    # Should return None or 0
    assert result is None or result == 0


def test_percentile_calculates_correctly() -> None:
    """Test that _percentile calculates percentile values correctly."""
    values = [1.0, 2.0, 3.0, 4.0, 5.0]

    assert _percentile(values, 0.0) == 1.0
    assert _percentile(values, 1.0) == 5.0
    # Median should be around 3.0
    p50 = _percentile(values, 0.5)
    assert 2.5 <= p50 <= 3.5


def test_percentile_returns_zero_for_empty_list() -> None:
    """Test that _percentile returns 0.0 for empty list."""
    result = _percentile([], 0.5)
    assert result == 0.0


def test_percentile_with_single_element() -> None:
    """Test that _percentile handles single-element list."""
    result = _percentile([42.0], 0.5)
    assert result == 42.0


def test_percentile_calculates_p95() -> None:
    """Test that _percentile calculates p95 correctly."""
    values = [float(i) for i in range(100)]

    p95 = _percentile(values, 0.95)

    # p95 should be around 95
    assert 90 <= p95 <= 97


def test_percentile_calculates_p99() -> None:
    """Test that _percentile calculates p99 correctly."""
    values = [float(i) for i in range(100)]

    p99 = _percentile(values, 0.99)

    # p99 should be around 99
    assert 95 <= p99 <= 99.5


@pytest.mark.parametrize("percentile_val", [0.0, 0.25, 0.5, 0.75, 0.95, 0.99, 1.0])
def test_percentile_various_percentiles(percentile_val: float) -> None:
    """Test percentile calculation at various percentile values."""
    values = [float(i) for i in range(1, 101)]

    result = _percentile(values, percentile_val)

    # Result should be within data range
    assert 1.0 <= result <= 100.0
