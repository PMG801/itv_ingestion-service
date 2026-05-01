from __future__ import annotations

from typing import Any

import pytest

from domain.itv_stations.transformers.llm_client import BaseLLMClient, LLMClientError, LLMUsage
from domain.itv_stations.transformers.llm_transformer import LLMTransformer


class _FakeLLMClient(BaseLLMClient):
    def __init__(
        self,
        *,
        mapped_items: list[dict[str, Any]] | None = None,
        error: LLMClientError | None = None,
        usage: LLMUsage | None = None,
    ) -> None:
        self._mapped_items = mapped_items or []
        self._error = error
        self._usage = usage or LLMUsage()

    async def get_normalized_mapping(
        self,
        *,
        source_system: str,
        minified_payloads: list[str],
    ) -> tuple[list[dict[str, Any]], LLMUsage]:
        if self._error is not None:
            raise self._error
        return self._mapped_items, self._usage


@pytest.mark.asyncio
async def test_llm_transformer_transform_async_success() -> None:
    fake_client = _FakeLLMClient(
        mapped_items=[
            {
                "raw_id": "BCN-001",
                "name": "  ITV Barcelona Nord  ",
                "address": "Carrer de la Industria 123",
                "city": "Barcelona",
                "province": "Barcelona",
                "postal_code": "08025",
                "latitude": "41.3851",
                "longitude": "2.1734",
                "phone": "932 123 456",
                "email": "info@itvbarcelona.cat",
            }
        ],
        usage=LLMUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
    )

    transformer = LLMTransformer(source_system="catalunya", llm_client=fake_client)

    stations = await transformer.transform_async({"id": "BCN-001", "nom": "ITV Barcelona Nord"})

    assert len(stations) == 1
    station = stations[0]
    assert station.raw_id == "BCN-001"
    assert station.name == "ITV Barcelona Nord"
    assert station.phone == "+34932123456"
    assert int(transformer.last_metrics["llm_token_usage"]) == 30


@pytest.mark.asyncio
async def test_llm_transformer_records_pydantic_errors() -> None:
    fake_client = _FakeLLMClient(mapped_items=[{"raw_id": "BCN-001"}])
    transformer = LLMTransformer(source_system="catalunya", llm_client=fake_client)

    stations = await transformer.transform_async({"id": "BCN-001"})

    assert stations == []
    assert int(transformer.last_metrics["llm_pydantic_validation_errors"]) >= 1
    assert any(item["reason"] in {"missing_name", "llm_pydantic_validation_error"} for item in transformer.rejected_items)


@pytest.mark.asyncio
async def test_llm_transformer_rejects_on_client_failure() -> None:
    fake_error = LLMClientError("boom", reason="llm_timeout")
    fake_client = _FakeLLMClient(error=fake_error)
    transformer = LLMTransformer(source_system="valencia", llm_client=fake_client)

    stations = await transformer.transform_async({"codigo": "VAL-001"})

    assert stations == []
    assert transformer.last_metrics["llm_last_error_reason"] == "llm_timeout"
    assert any(item["reason"] == "llm_timeout" for item in transformer.rejected_items)
