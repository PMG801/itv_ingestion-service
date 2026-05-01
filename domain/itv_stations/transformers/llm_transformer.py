"""LLM-based transformer with learned mapping rules caching and provider abstraction."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import xml.etree.ElementTree as ET
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from time import perf_counter
from typing import Any

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from domain.itv_stations.schemas import NormalizedStation
from domain.itv_stations.transformers.base import BaseTransformer
from domain.itv_stations.transformers.llm_client import (
    BaseLLMClient,
    LLMClientError,
    LLMInvalidJSONError,
    LLMUsage,
    get_llm_client,
)

logger = logging.getLogger(__name__)


class LLMTransformer(BaseTransformer):
    """Transformer that delegates semantic mapping to an external LLM API with learned rules caching.
    
    This transformer implements a two-tier approach:
    1. Rules cache: Attempts to find learned mapping rules for the source+province_type
    2. LLM fallback: If no rule exists, generates rule via LLM and persists it
    
    The rules cache significantly reduces LLM inference calls for repeated source types.
    """

    def __init__(
        self, 
        source_system: str = "catalunya", 
        llm_client: BaseLLMClient | None = None,
        db_session: AsyncSession | None = None,
    ) -> None:
        super().__init__(source_system=source_system.lower().strip())
        self._llm_client = llm_client or get_llm_client()
        self._db_session = db_session
        self.last_generated_mapping: list[dict[str, Any]] = []
        self.last_metrics: dict[str, int | float | str] = self._empty_metrics()
        self._active_rule: dict[str, Any] | None = None

    def _empty_metrics(self) -> dict[str, int | float | str]:
        return {
            "llm_inference_ms": 0.0,
            "llm_pydantic_validation_errors": 0,
            "llm_token_usage": 0,
            "llm_prompt_tokens": 0,
            "llm_completion_tokens": 0,
            "llm_last_error_reason": "",
            "llm_rule_cache_hit": 0,
            "llm_rule_cache_miss": 0,
            "llm_rule_generation_calls": 0,
            "llm_rule_application_errors": 0,
        }

    async def transform_async(self, raw_payload: Any) -> list[NormalizedStation]:
        """Async transform path used by the normalizer worker."""
        return await self.transform_batch_async([raw_payload])

    async def transform_batch_async(self, raw_payloads: Sequence[Any]) -> list[NormalizedStation]:
        """Async batch transform with rules caching and LLM fallback."""
        self.reset_rejections()
        self.last_generated_mapping = []
        self.last_metrics = self._empty_metrics()

        raw_items = self._expand_payload_items(raw_payloads)
        minified_payloads = [self._minify_payload(item) for item in raw_items]

        if not minified_payloads:
            return []

        # Determine province type from payloads for rule lookup
        province_type = self._extract_province_type(raw_items)
        
        # Attempt to load active rule from cache if DB session available
        active_rule = None
        if self._db_session is not None:
            try:
                from core.database.queries import get_active_llm_mapping_rule
                active_rule = await get_active_llm_mapping_rule(
                    self._db_session, self.source_system, province_type
                )
                if active_rule:
                    self.last_metrics["llm_rule_cache_hit"] = 1
                    logger.debug(
                        f"Rule cache HIT for source={self.source_system} province_type={province_type}"
                    )
                else:
                    self.last_metrics["llm_rule_cache_miss"] = 1
            except Exception as exc:
                logger.warning(f"Failed to load rule from cache: {exc}")
                self.last_metrics["llm_rule_cache_miss"] = 1
        else:
            # No DB session, treat as cache miss (will invoke LLM)
            self.last_metrics["llm_rule_cache_miss"] = 1

        # Apply rule if available, otherwise invoke LLM
        if active_rule:
            try:
                mapped_items = self._apply_mapping_rule(minified_payloads, active_rule["field_mapping"])
                self.last_generated_mapping = mapped_items
            except Exception as exc:
                logger.warning(f"Rule application failed, falling back to LLM: {exc}")
                self.last_metrics["llm_rule_application_errors"] = 1
                mapped_items, usage = await self._invoke_llm_with_persistence(
                    minified_payloads, province_type
                )
        else:
            # No rule available, invoke LLM and persist new rule
            mapped_items, usage = await self._invoke_llm_with_persistence(
                minified_payloads, province_type
            )

        # Build and validate stations from mapped items
        stations: list[NormalizedStation] = []
        pydantic_errors = 0

        for mapped in mapped_items:
            station = self._build_station(mapped)
            if station is None:
                if self.last_metrics["llm_last_error_reason"] == "":
                    self.last_metrics["llm_last_error_reason"] = "llm_pydantic_validation_error"
                pydantic_errors += 1
                continue
            stations.append(station)

        deduped = self._check_duplicate_within_message(stations)
        deduped = self._check_duplicate_contact_fields(deduped)

        self.last_metrics["llm_pydantic_validation_errors"] = pydantic_errors

        return deduped

    async def _invoke_llm_with_persistence(
        self, minified_payloads: Sequence[str], province_type: str
    ) -> tuple[list[dict[str, Any]], LLMUsage]:
        """Invoke LLM to generate mapping, persist rule if successful."""
        llm_started_at = datetime.now(timezone.utc)
        started = perf_counter()

        try:
            mapped_items, usage = await self._llm_client.get_normalized_mapping(
                source_system=self.source_system,
                minified_payloads=minified_payloads,
            )
        except LLMClientError as exc:
            self.last_metrics["llm_last_error_reason"] = exc.reason
            error_detail = f" | http_status={exc.http_status}" if exc.http_status else ""
            if exc.response_detail:
                error_detail += f" | response={exc.response_detail[:200]}"
            logger.warning(
                "LLM mapping failed for source=%s reason=%s%s",
                self.source_system,
                exc.reason,
                error_detail,
            )
            self.record_rejection(exc.reason, {"source_system": self.source_system})
            return [], LLMUsage()
        except Exception as exc:  # pragma: no cover - defensive fallback
            self.last_metrics["llm_last_error_reason"] = "llm_unexpected_error"
            self.record_rejection("llm_unexpected_error", {"error": str(exc)})
            logger.error("Unexpected LLM mapping error: %s", exc, exc_info=True)
            return [], LLMUsage()

        llm_finished_at = datetime.now(timezone.utc)
        self.last_metrics["llm_inference_ms"] = round((perf_counter() - started) * 1000, 3)
        self.last_metrics["llm_prompt_tokens"] = usage.prompt_tokens
        self.last_metrics["llm_completion_tokens"] = usage.completion_tokens
        self.last_metrics["llm_token_usage"] = usage.total_tokens
        self.last_metrics["llm_rule_generation_calls"] = 1

        # Extract and persist mapping rule if we have mapped items and DB session
        if mapped_items and self._db_session is not None:
            try:
                field_mapping = self._extract_field_mapping(mapped_items)
                sample_signature = self._compute_schema_signature(mapped_items[0] if mapped_items else {})
                
                from core.database.queries import create_llm_mapping_rule
                from core.config import settings
                
                await create_llm_mapping_rule(
                    self._db_session,
                    source_system=self.source_system,
                    province_type=province_type,
                    field_mapping=field_mapping,
                    llm_model=settings.LLM_MODEL,
                    llm_prompt_version="1.0",
                    confidence_score=0.95,
                    sample_schema_signature=sample_signature,
                )
                await self._db_session.commit()
                logger.info(
                    f"Persisted new mapping rule for source={self.source_system} province_type={province_type}"
                )
            except Exception as exc:
                logger.warning(f"Failed to persist mapping rule: {exc}")
                await self._db_session.rollback()

        return mapped_items, usage

    def transform(self, raw_payload: Any) -> list[NormalizedStation]:
        """Synchronous wrapper required by BaseTransformer contract."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.transform_async(raw_payload))

        raise RuntimeError(
            "LLMTransformer.transform() cannot run inside an active event loop. "
            "Use await transform_async() instead."
        )

    def transform_batch(self, raw_payloads: Sequence[Any]) -> list[NormalizedStation]:
        """Synchronous batch wrapper for scripts without active event loop."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.transform_batch_async(raw_payloads))

        raise RuntimeError(
            "LLMTransformer.transform_batch() cannot run inside an active event loop. "
            "Use await transform_batch_async() instead."
        )

    def _expand_payload_items(self, raw_payloads: Sequence[Any]) -> list[Any]:
        """Flatten standard source wrappers into per-item payloads."""
        expanded: list[Any] = []
        for raw_payload in raw_payloads:
            if isinstance(raw_payload, dict):
                dict_payload = dict(raw_payload)
                stations_obj = dict_payload.get("stations")
                if isinstance(stations_obj, list):
                    expanded.extend(stations_obj)
                    continue

                estaciones_obj = dict_payload.get("estaciones")
                if isinstance(estaciones_obj, list):
                    expanded.extend(estaciones_obj)
                    continue

            if isinstance(raw_payload, list):
                expanded.extend(raw_payload)
                continue

            expanded.append(raw_payload)

        return expanded

    def _minify_payload(self, payload: Any) -> str:
        """Compact payload representation to reduce token usage."""
        if isinstance(payload, Mapping):
            return json.dumps(dict(payload), ensure_ascii=False, separators=(",", ":"))

        if isinstance(payload, list):
            return json.dumps(list(payload), ensure_ascii=False, separators=(",", ":"))

        if isinstance(payload, str):
            stripped = payload.strip()
            if not stripped:
                return ""

            if stripped.startswith("<"):
                try:
                    root = ET.fromstring(stripped)
                    return ET.tostring(root, encoding="unicode", method="xml")
                except ET.ParseError:
                    return " ".join(stripped.split())

            try:
                loaded = json.loads(stripped)
                return json.dumps(loaded, ensure_ascii=False, separators=(",", ":"))
            except json.JSONDecodeError:
                return " ".join(stripped.split())

        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)

    def _build_station(self, mapped: Mapping[str, Any]) -> NormalizedStation | None:
        """Post-process LLM mapping in Python and validate strictly with Pydantic."""
        if not isinstance(mapped, Mapping):
            self.record_rejection("llm_invalid_json", {"value": str(mapped)})
            return None

        raw_id = self._as_optional_str(mapped.get("raw_id") or mapped.get("id"))
        name = self._as_optional_str(mapped.get("name"))

        if not raw_id:
            self.record_rejection("missing_raw_id", dict(mapped))
            return None
        if not name:
            self.record_rejection("missing_name", dict(mapped))
            return None

        station_payload: dict[str, Any] = {
            "station_id": self._generate_station_id(raw_id),
            "name": name,
            "address": self._as_optional_str(mapped.get("address")),
            "city": self._as_optional_str(mapped.get("city")),
            "province": self._as_optional_str(mapped.get("province")),
            "postal_code": self._clean_postal_code(self._as_optional_str(mapped.get("postal_code"))),
            "latitude": self._parse_float(mapped.get("latitude")),
            "longitude": self._parse_float(mapped.get("longitude")),
            "phone": self._clean_phone(self._as_optional_str(mapped.get("phone"))),
            "email": self._as_optional_str(mapped.get("email")),
            "source_system": self.source_system,
            "raw_id": raw_id,
        }

        try:
            station = NormalizedStation.model_validate(station_payload)
        except ValidationError:
            self.record_rejection("llm_pydantic_validation_error", dict(mapped))
            return None
        except Exception:
            self.record_rejection("llm_pydantic_validation_error", dict(mapped))
            return None

        is_valid, validation_reason = self._validate_station(station)
        if not is_valid:
            self.record_rejection(validation_reason or "validation_failed", dict(mapped))
            return None

        return station

    def _extract_province_type(self, raw_items: list[Any]) -> str:
        """Extract province type from first item to use as rule lookup key."""
        if not raw_items:
            return "unknown"
        
        first_item = raw_items[0]
        if not isinstance(first_item, dict):
            return "unknown"
        
        # Try common province field names
        province = (
            first_item.get("province") 
            or first_item.get("provincia") 
            or first_item.get("PROVINCIA")
            or "unknown"
        )
        
        if isinstance(province, str):
            return province.strip().lower()
        return str(province).lower()

    def _apply_mapping_rule(
        self, minified_payloads: Sequence[str], field_mapping: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Apply learned mapping rule locally without LLM call."""
        mapped_items: list[dict[str, Any]] = []
        
        for payload_str in minified_payloads:
            try:
                parsed = json.loads(payload_str)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse minified payload: {payload_str}")
                continue
            
            if not isinstance(parsed, dict):
                continue
            
            # Apply field mapping: source_field -> target_field
            mapped_item: dict[str, Any] = {}
            for source_field, target_field in field_mapping.items():
                if source_field in parsed:
                    mapped_item[target_field] = parsed[source_field]
            
            # Ensure required fields exist (fallback to source if mapping missing)
            for required_field in ["raw_id", "name"]:
                if required_field not in mapped_item and "raw_id" in parsed:
                    mapped_item["raw_id"] = parsed.get("raw_id") or parsed.get("id")
                if required_field not in mapped_item and "name" in parsed:
                    mapped_item["name"] = parsed.get("name") or parsed.get("nombre")
            
            mapped_items.append(mapped_item)
        
        return mapped_items

    def _extract_field_mapping(self, mapped_items: list[dict[str, Any]]) -> dict[str, str]:
        """Extract field mapping pattern from LLM results."""
        if not mapped_items:
            return {}
        
        # Use keys from first item as the mapping target schema
        first_item = mapped_items[0]
        if not isinstance(first_item, dict):
            return {}
        
        # Simple mapping: target_field -> target_field (learned schema)
        mapping: dict[str, str] = {}
        for key in first_item.keys():
            mapping[key] = key
        
        return mapping

    def _compute_schema_signature(self, item: dict[str, Any]) -> str:
        """Compute SHA256 signature of item schema for tracking."""
        keys_sorted = sorted(item.keys())
        schema_str = json.dumps(keys_sorted)
        return hashlib.sha256(schema_str.encode()).hexdigest()[:16]

    async def validate_prompt_contract_async(self) -> None:
        """Internal utility for testing strict JSON behavior."""
        try:
            await self._llm_client.get_normalized_mapping(
                source_system=self.source_system,
                minified_payloads=["{}"],
            )
        except LLMInvalidJSONError as exc:
            self.last_metrics["llm_last_error_reason"] = exc.reason
