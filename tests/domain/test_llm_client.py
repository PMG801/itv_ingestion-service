from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from core.config import settings
from domain.itv_stations.transformers import llm_client as llm_client_module
from domain.itv_stations.transformers.llm_client import (
    GitHubModelsClient,
    GroqClient,
    LLMInvalidJSONError,
    LLMRateLimitError,
    LLMTimeoutError,
)


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, Any], text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeAsyncClient:
    def __init__(self, response: _FakeResponse | None = None, raise_timeout: bool = False) -> None:
        self._response = response
        self._raise_timeout = raise_timeout

    async def __aenter__(self) -> _FakeAsyncClient:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        return None

    async def post(self, *args: Any, **kwargs: Any) -> _FakeResponse:
        if self._raise_timeout:
            raise httpx.TimeoutException("timeout")
        assert self._response is not None
        return self._response


class _FakeChatCompletionsClient:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.calls: list[dict[str, Any]] = []

    def complete(self, *args: Any, **kwargs: Any) -> SimpleNamespace:
        self.calls.append({"args": args, "kwargs": kwargs})
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='[{"raw_id":"A1","name":"ITV A"}]'))],
            usage=SimpleNamespace(prompt_tokens=7, completion_tokens=4, total_tokens=11),
        )


@pytest.mark.asyncio
async def test_llm_client_parses_strict_json_array(monkeypatch: pytest.MonkeyPatch) -> None:
    client = GroqClient()
    client._api_key = "test-key"  # type: ignore[attr-defined]

    payload = {
        "choices": [{"message": {"content": '[{"raw_id":"A1","name":"ITV A"}]'}}],
        "usage": {"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20},
    }

    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: _FakeAsyncClient(_FakeResponse(200, payload)))

    mapped, usage = await client.get_normalized_mapping(
        source_system="catalunya",
        minified_payloads=["{\"id\":\"A1\"}"],
    )

    assert len(mapped) == 1
    assert mapped[0]["raw_id"] == "A1"
    assert usage.total_tokens == 20


@pytest.mark.asyncio
async def test_github_models_client_parses_strict_json_array(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "GITHUB_TOKEN", "test-token")
    monkeypatch.setattr(settings, "GITHUB_MODELS_ENDPOINT", "https://models.github.ai/inference")
    monkeypatch.setattr(llm_client_module, "ChatCompletionsClient", _FakeChatCompletionsClient)
    client = GitHubModelsClient()

    mapped, usage = await client.get_normalized_mapping(
        source_system="catalunya",
        minified_payloads=["{\"id\":\"A1\"}"],
    )

    assert len(mapped) == 1
    assert mapped[0]["raw_id"] == "A1"
    assert usage.total_tokens == 11


@pytest.mark.asyncio
async def test_llm_client_rejects_prefixed_non_json_output(monkeypatch: pytest.MonkeyPatch) -> None:
    client = GroqClient()
    client._api_key = "test-key"  # type: ignore[attr-defined]

    payload = {
        "choices": [
            {
                "message": {
                    "content": 'Aqui tienes el JSON: [{"raw_id":"A1","name":"ITV A"}]'
                }
            }
        ]
    }

    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: _FakeAsyncClient(_FakeResponse(200, payload)))

    with pytest.raises(LLMInvalidJSONError, match="must start with '\\['"):
        await client.get_normalized_mapping(
            source_system="catalunya",
            minified_payloads=["{\"id\":\"A1\"}"],
        )


@pytest.mark.asyncio
async def test_llm_client_raises_rate_limit_on_429(monkeypatch: pytest.MonkeyPatch) -> None:
    client = GroqClient()
    client._api_key = "test-key"  # type: ignore[attr-defined]

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda *args, **kwargs: _FakeAsyncClient(_FakeResponse(429, {}, text="rate limit")),
    )

    with pytest.raises(LLMRateLimitError):
        await client.get_normalized_mapping(
            source_system="valencia",
            minified_payloads=["{\"codigo\":\"V1\"}"],
        )


@pytest.mark.asyncio
async def test_llm_client_raises_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    client = GroqClient()
    client._api_key = "test-key"  # type: ignore[attr-defined]

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda *args, **kwargs: _FakeAsyncClient(raise_timeout=True),
    )

    with pytest.raises(LLMTimeoutError):
        await client.get_normalized_mapping(
            source_system="galicia",
            minified_payloads=["{\"id\":\"G1\"}"],
        )
