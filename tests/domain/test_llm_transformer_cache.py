"""Tests for LLM transformer caching and rule persistence functionality."""

from __future__ import annotations

from typing import Any
from datetime import datetime, timezone

import pytest

from domain.itv_stations.transformers.llm_client import (
    BaseLLMClient,
    LLMClientError,
    LLMUsage,
)
from domain.itv_stations.transformers.llm_transformer import LLMTransformer
from domain.itv_stations.models import LLMMappingRule


class _FakeLLMClientWithRuleGen(BaseLLMClient):
    """Fake LLM client that generates deterministic mappings."""

    def __init__(self, mapped_items: list[dict[str, Any]] | None = None) -> None:
        self._mapped_items = mapped_items or [
            {
                "raw_id": "A1",
                "name": "Station A",
                "address": "Addr A",
                "province": "Barcelona",
                "postal_code": "08001",
                "latitude": 41.3851,
                "longitude": 2.1734,
                "phone": "932123456",
                "email": "a@example.com",
            }
        ]

    async def get_normalized_mapping(
        self,
        *,
        source_system: str,
        minified_payloads: list[str],
    ) -> tuple[list[dict[str, Any]], LLMUsage]:
        return self._mapped_items, LLMUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150)


@pytest.mark.asyncio
async def test_llm_transformer_cache_miss_invokes_llm() -> None:
    """Test that cache miss invokes LLM."""
    transformer = LLMTransformer(
        source_system="catalunya",
        llm_client=_FakeLLMClientWithRuleGen(),
        db_session=None,  # No DB session = no caching
    )

    # Just verify that metrics are set correctly for cache miss scenario
    # (validation may reject items, but metrics should show LLM was called)
    await transformer.transform_batch_async(
        [{"raw_id": "A1", "name": "Station A", "province": "Barcelona"}]
    )

    assert transformer.last_metrics["llm_rule_cache_miss"] == 1
    assert transformer.last_metrics["llm_token_usage"] == 150


@pytest.mark.asyncio
async def test_llm_transformer_extracts_province_type() -> None:
    """Test that province_type is extracted from payloads."""
    transformer = LLMTransformer(source_system="valencia")

    province_type = transformer._extract_province_type(
        [{"id": "V1", "name": "Station V", "province": "Valencia"}]
    )

    assert province_type == "valencia"


@pytest.mark.asyncio
async def test_llm_transformer_applies_mapping_rule() -> None:
    """Test local application of learned mapping rule."""
    transformer = LLMTransformer(source_system="galicia")

    field_mapping = {
        "id": "raw_id",
        "nombre": "name",
        "localidad": "city",
    }

    minified_payloads = ['{"id":"G1","nombre":"Station G","localidad":"Santiago"}']

    mapped_items = transformer._apply_mapping_rule(minified_payloads, field_mapping)

    assert len(mapped_items) == 1
    assert mapped_items[0]["raw_id"] == "G1"
    assert mapped_items[0]["name"] == "Station G"
    assert mapped_items[0]["city"] == "Santiago"


@pytest.mark.asyncio
async def test_llm_transformer_computes_schema_signature() -> None:
    """Test schema signature computation."""
    transformer = LLMTransformer(source_system="catalunya")

    item1 = {"raw_id": "A1", "name": "S1", "province": "Barcelona"}
    sig1 = transformer._compute_schema_signature(item1)

    item2 = {"raw_id": "A2", "name": "S2", "province": "Barcelona"}
    sig2 = transformer._compute_schema_signature(item2)

    # Same schema structure should produce same signature (only keys matter)
    assert sig1 == sig2
    assert len(sig1) == 16  # SHA256 truncated to 16 chars


@pytest.mark.asyncio
async def test_llm_transformer_extracts_field_mapping() -> None:
    """Test extraction of field mapping from LLM results."""
    transformer = LLMTransformer(source_system="valencia")

    mapped_items = [
        {
            "raw_id": "V1",
            "name": "Station V",
            "province": "Valencia",
            "postal_code": "46001",
            "latitude": 39.4699,
            "longitude": -0.3763,
        }
    ]

    field_mapping = transformer._extract_field_mapping(mapped_items)

    # Mapping should include all keys from first item
    assert "raw_id" in field_mapping
    assert "name" in field_mapping
    assert "province" in field_mapping
    assert "postal_code" in field_mapping


@pytest.mark.asyncio
async def test_llm_transformer_metrics_on_cache_miss() -> None:
    """Test that cache miss metrics are recorded."""
    transformer = LLMTransformer(
        source_system="catalunya",
        llm_client=_FakeLLMClientWithRuleGen(),
        db_session=None,
    )

    await transformer.transform_batch_async(
        [{"raw_id": "A1", "name": "Station A", "province": "Barcelona"}]
    )

    assert transformer.last_metrics["llm_rule_cache_miss"] == 1
    assert transformer.last_metrics["llm_rule_cache_hit"] == 0
    assert transformer.last_metrics["llm_rule_generation_calls"] == 1


@pytest.mark.asyncio
async def test_llm_transformer_backward_compatibility_no_db_session() -> None:
    """Test backward compatibility when no DB session provided."""
    fake_client = _FakeLLMClientWithRuleGen()
    transformer = LLMTransformer(
        source_system="galicia",
        llm_client=fake_client,
        db_session=None,  # Simulate no database
    )

    # Should work without DB session (classic behavior)
    # Verify metrics are recorded even without DB
    await transformer.transform_batch_async(
        [{"raw_id": "G1", "name": "Station G", "province": "Galicia"}]
    )

    # Without DB session, cache miss should be set to 1
    assert transformer.last_metrics.get("llm_rule_cache_miss", 0) == 1
