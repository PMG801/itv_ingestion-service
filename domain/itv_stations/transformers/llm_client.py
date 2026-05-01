"""LLM client abstraction with support for multiple providers (Groq, GitHub Models)."""

from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import httpx

from core.config import settings

# Free-tier safety: serialize outbound LLM requests to reduce 429 errors.
_GROQ_RATE_LIMIT_SEMAPHORE = asyncio.Semaphore(1)
_GITHUB_MODELS_RATE_LIMIT_SEMAPHORE = asyncio.Semaphore(1)


@dataclass(slots=True)
class LLMUsage:
    """Token usage reported by Groq/OpenAI-compatible response."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class LLMClientError(Exception):
    """Base class for all LLM client errors."""

    def __init__(self, message: str, reason: str, *, http_status: int | None = None, response_detail: str = "") -> None:
        super().__init__(message)
        self.reason = reason
        self.http_status = http_status
        self.response_detail = response_detail


class LLMTimeoutError(LLMClientError):
    """Raised on request timeout."""


class LLMRateLimitError(LLMClientError):
    """Raised on HTTP 429."""


class LLMHTTPError(LLMClientError):
    """Raised on unexpected HTTP errors."""


class LLMInvalidJSONError(LLMClientError):
    """Raised when model output is not strict JSON array."""


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients."""

    @abstractmethod
    async def get_normalized_mapping(
        self,
        *,
        source_system: str,
        minified_payloads: Sequence[str],
    ) -> tuple[list[dict[str, Any]], LLMUsage]:
        """Request semantic mapping and return strict JSON array plus usage."""
        pass

    @staticmethod
    def _build_system_prompt(source_system: str) -> str:
        """Hard constraint prompt: output JSON only, no extra text."""
        return (
            "You are a data mapping engine. "
            "Map each raw item to the exact schema below and return ONLY a JSON array. "
            "Do not include markdown, code fences, comments, explanations, or prefixes like "
            "'Aqui tienes el JSON:'.\n\n"
            "Output schema per object:\n"
            "{\n"
            '  "raw_id": "string",\n'
            '  "name": "string",\n'
            '  "address": "string|null",\n'
            '  "city": "string|null",\n'
            '  "province": "string|null",\n'
            '  "postal_code": "string|null",\n'
            '  "latitude": "number|string|null",\n'
            '  "longitude": "number|string|null",\n'
            '  "phone": "string|null",\n'
            '  "email": "string|null"\n'
            "}\n\n"
            "Rules:\n"
            "- Preserve item order from input.\n"
            "- Use null if value is not present.\n"
            "- Never invent data.\n"
            f"- Source system is '{source_system}'.\n"
            "- Return only the JSON array and nothing else."
        )

    @staticmethod
    def _build_user_prompt(minified_payloads: Sequence[str]) -> str:
        """Create compact user prompt payload."""
        return (
            "Map the following minified raw records to the schema. "
            "Return only a JSON array with one output object per input item in the same order.\n"
            f"RAW_ITEMS={json.dumps(list(minified_payloads), ensure_ascii=False, separators=(',', ':'))}"
        )

    @staticmethod
    def _extract_content(body: dict[str, Any]) -> str:
        """Extract first completion content from OpenAI-compatible response."""
        choices = body.get("choices")
        if not isinstance(choices, list) or not choices:
            raise LLMInvalidJSONError("Missing choices in LLM response", reason="llm_invalid_json")

        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise LLMInvalidJSONError("Invalid choice format", reason="llm_invalid_json")

        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise LLMInvalidJSONError("Missing message object", reason="llm_invalid_json")

        content = message.get("content")
        if not isinstance(content, str):
            raise LLMInvalidJSONError("Missing message content", reason="llm_invalid_json")

        return content.strip()

    @staticmethod
    def _parse_strict_json_array(content: str) -> list[dict[str, Any]]:
        """Parse strict JSON array and reject any wrapped text."""
        if not content:
            raise LLMInvalidJSONError("Empty content from LLM", reason="llm_invalid_json")

        if not content.startswith("["):
            raise LLMInvalidJSONError(
                "LLM output must start with '[' and contain only JSON array",
                reason="llm_invalid_json",
            )

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise LLMInvalidJSONError(
                f"LLM output is not valid JSON: {exc}",
                reason="llm_invalid_json",
            ) from exc

        if not isinstance(parsed, list):
            raise LLMInvalidJSONError(
                "LLM output must be a JSON array",
                reason="llm_invalid_json",
            )

        normalized: list[dict[str, Any]] = []
        for item in parsed:
            if not isinstance(item, dict):
                raise LLMInvalidJSONError(
                    "Every item in LLM output array must be a JSON object",
                    reason="llm_invalid_json",
                )
            normalized.append(item)

        return normalized

    @staticmethod
    def _extract_usage(body: dict[str, Any]) -> LLMUsage:
        """Extract usage block if available."""
        usage = body.get("usage")
        if not isinstance(usage, dict):
            return LLMUsage()

        prompt_tokens = usage.get("prompt_tokens")
        completion_tokens = usage.get("completion_tokens")
        total_tokens = usage.get("total_tokens")

        return LLMUsage(
            prompt_tokens=prompt_tokens if isinstance(prompt_tokens, int) else 0,
            completion_tokens=completion_tokens if isinstance(completion_tokens, int) else 0,
            total_tokens=total_tokens if isinstance(total_tokens, int) else 0,
        )


class GroqClient(BaseLLMClient):
    """Async Groq client for semantic mapping with strict JSON-only responses."""

    def __init__(self) -> None:
        self._api_key = settings.GROQ_API_KEY.strip()
        self._model = settings.LLM_MODEL
        self._temperature = float(settings.LLM_TEMPERATURE)
        self._timeout = float(settings.LLM_REQUEST_TIMEOUT_S)
        self._base_url = "https://api.groq.com/openai/v1/chat/completions"

    async def get_normalized_mapping(
        self,
        *,
        source_system: str,
        minified_payloads: Sequence[str],
    ) -> tuple[list[dict[str, Any]], LLMUsage]:
        """Request semantic mapping and return strict JSON array plus usage."""
        if not self._api_key:
            raise LLMClientError("Missing GROQ_API_KEY", reason="llm_missing_api_key")

        if not minified_payloads:
            return [], LLMUsage()

        system_prompt = self._build_system_prompt(source_system)
        user_prompt = self._build_user_prompt(minified_payloads)

        request_payload: dict[str, Any] = {
            "model": self._model,
            "temperature": self._temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        async with _GROQ_RATE_LIMIT_SEMAPHORE:
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.post(
                        self._base_url,
                        headers=headers,
                        json=request_payload,
                    )
            except httpx.TimeoutException as exc:
                raise LLMTimeoutError(
                    f"Groq request timed out after {self._timeout:.0f}s",
                    reason="llm_timeout",
                ) from exc
            except httpx.RequestError as exc:
                raise LLMHTTPError(
                    f"Groq request failed: {exc}",
                    reason="llm_http_error",
                ) from exc

        if response.status_code == 429:
            raise LLMRateLimitError(
                "Groq rate limit exceeded",
                reason="llm_rate_limited",
                http_status=429,
            )
        if response.status_code >= 400:
            raise LLMHTTPError(
                f"Groq HTTP {response.status_code}: {response.text[:400]}",
                reason="llm_http_error",
                http_status=response.status_code,
                response_detail=response.text[:500],
            )

        body = response.json()
        content = self._extract_content(body)
        parsed = self._parse_strict_json_array(content)
        usage = self._extract_usage(body)
        return parsed, usage


class GitHubModelsClient(BaseLLMClient):
    """GitHub Models client (Foundry) for semantic mapping with strict JSON-only responses."""

    def __init__(self) -> None:
        self._token = settings.GITHUB_TOKEN.strip()
        self._model = settings.LLM_MODEL
        self._temperature = float(settings.LLM_TEMPERATURE)
        self._timeout = float(settings.LLM_REQUEST_TIMEOUT_S)
        self._base_url = settings.GITHUB_MODELS_ENDPOINT.rstrip("/")

        if not self._token:
            raise LLMClientError("Missing GITHUB_TOKEN", reason="llm_missing_api_key")

    async def get_normalized_mapping(
        self,
        *,
        source_system: str,
        minified_payloads: Sequence[str],
    ) -> tuple[list[dict[str, Any]], LLMUsage]:
        """Request semantic mapping and return strict JSON array plus usage."""
        if not minified_payloads:
            return [], LLMUsage()

        system_prompt = self._build_system_prompt(source_system)
        user_prompt = self._build_user_prompt(minified_payloads)

        # Retry on 429 with exponential backoff; SDK uses the Foundry endpoint and token directly.
        max_attempts = 3
        attempt = 0
        response = None

        async with _GITHUB_MODELS_RATE_LIMIT_SEMAPHORE:
            while attempt < max_attempts:
                attempt += 1
                try:
                    client = ChatCompletionsClient(
                        endpoint=self._base_url,
                        credential=AzureKeyCredential(self._token),
                    )
                    response = client.complete(
                        messages=[
                            SystemMessage(system_prompt),
                            UserMessage(user_prompt),
                        ],
                        temperature=self._temperature,
                        top_p=1.0,
                        model=self._model,
                    )
                except ServiceRequestError as exc:
                    raise LLMTimeoutError(
                        f"GitHub Models request timed out after {self._timeout:.0f}s",
                        reason="llm_timeout",
                    ) from exc
                except HttpResponseError as exc:
                    status_code = getattr(exc, "status_code", None)
                    if status_code == 429:
                        if attempt >= max_attempts:
                            raise LLMRateLimitError(
                                "GitHub Models rate limit exceeded",
                                reason="llm_rate_limited",
                                http_status=429,
                            ) from exc
                        backoff = (2 ** (attempt - 1)) + (0.1 * attempt)
                        await asyncio.sleep(backoff)
                        continue
                    raise LLMHTTPError(
                        f"GitHub Models HTTP {status_code or 'error'}: {exc}",
                        reason="llm_http_error",
                        http_status=status_code,
                        response_detail=str(exc),
                    ) from exc
                except Exception as exc:
                    raise LLMHTTPError(
                        f"GitHub Models request failed: {exc}",
                        reason="llm_http_error",
                    ) from exc

                if response is None:
                    break
                break

        content = response.choices[0].message.content.strip()
        parsed = self._parse_strict_json_array(content)
        usage = LLMUsage(
            prompt_tokens=getattr(getattr(response, "usage", None), "prompt_tokens", 0) or 0,
            completion_tokens=getattr(getattr(response, "usage", None), "completion_tokens", 0) or 0,
            total_tokens=getattr(getattr(response, "usage", None), "total_tokens", 0) or 0,
        )
        return parsed, usage


class LLMClientFactory:
    """Factory for creating LLM clients based on configured provider."""

    @staticmethod
    def create() -> BaseLLMClient:
        """Create LLM client based on LLM_PROVIDER setting.

        Returns:
            BaseLLMClient: Groq or GitHub Models client.

        Raises:
            ValueError: If provider is not supported or configuration is missing.
        """
        provider = settings.LLM_PROVIDER.strip().lower()

        if provider == "groq":
            return GroqClient()
        elif provider == "github_models":
            return GitHubModelsClient()
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")


# Global LLM client instance (lazy-initialized on first use)
_llm_client_instance: BaseLLMClient | None = None


def get_llm_client() -> BaseLLMClient:
    """Get or create the global LLM client instance."""
    global _llm_client_instance
    if _llm_client_instance is None:
        _llm_client_instance = LLMClientFactory.create()
    return _llm_client_instance


# Legacy compatibility: direct exports for existing code
async def get_normalized_mapping(
    *,
    source_system: str,
    minified_payloads: Sequence[str],
) -> tuple[list[dict[str, Any]], LLMUsage]:
    """Compatibility wrapper for existing code."""
    client = get_llm_client()
    return await client.get_normalized_mapping(source_system=source_system, minified_payloads=minified_payloads)


# Export exception classes for backward compatibility
__all__ = [
    "LLMUsage",
    "LLMClientError",
    "LLMTimeoutError",
    "LLMRateLimitError",
    "LLMHTTPError",
    "LLMInvalidJSONError",
    "BaseLLMClient",
    "GroqClient",
    "GitHubModelsClient",
    "LLMClientFactory",
    "get_llm_client",
    "get_normalized_mapping",
]
