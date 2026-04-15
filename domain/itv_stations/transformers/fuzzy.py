"""
Fuzzy data transformer based on field-name similarity.
"""

from __future__ import annotations

from collections.abc import Mapping
from time import perf_counter
from typing import Any

from rapidfuzz.distance import JaroWinkler

from core.config import settings
from domain.itv_stations.schemas import NormalizedStation
from domain.itv_stations.transformers.base import BaseTransformer


class FuzzyTransformer(BaseTransformer):
    """Map payload fields to canonical schema using fuzzy matching."""

    _canonical_fields: tuple[str, ...] = (
        "raw_id",
        "name",
        "address",
        "city",
        "province",
        "postal_code",
        "latitude",
        "longitude",
        "phone",
        "email",
    )
    _required_fields: tuple[str, ...] = ("raw_id", "name")
    _top_candidates: int = 3
    def __init__(self, source_system: str = "catalunya") -> None:
        super().__init__(source_system=source_system.lower().strip())
        self.last_metrics: dict[str, float | int] = {
            "similarity_compute_ms": 0.0,
            "confidence_mean": 0.0,
            "low_confidence_count": 0,
            "rejected_by_fuzzy_count": 0,
            "_confidence_sum": 0.0,
            "_confidence_count": 0,
        }

    def _increment_metric(self, metric_name: str, amount: int = 1) -> None:
        self.last_metrics[metric_name] = int(self.last_metrics.get(metric_name, 0)) + amount

    def _similarity_score(self, source_field: str, target_field: str) -> float:
        return float(JaroWinkler.normalized_similarity(source_field, target_field))

    def _map_payload_fields(
        self, payload: Mapping[str, object]
    ) -> tuple[dict[str, object], list[dict[str, object]], list[str], list[float]]:
        mapped: dict[str, object] = {}
        mapping_trace: list[dict[str, object]] = []
        low_confidence_fields: list[str] = []
        accepted_scores: list[float] = []

        payload_fields = [(str(key), key) for key in payload.keys()]

        for target_field in self._canonical_fields:
            ranked: list[tuple[str, object, float]] = sorted(
                (
                    (
                        source_field_name,
                        source_field_original,
                        self._similarity_score(source_field_name, target_field),
                    )
                    for source_field_name, source_field_original in payload_fields
                ),
                key=lambda item: item[2],
                reverse=True,
            )

            candidates = [
                {"field": item[0], "score": round(item[2], 4)}
                for item in ranked[: self._top_candidates]
                if item[2] > 0
            ]

            if ranked:
                best_name, best_original, best_score = ranked[0]
                trace_entry: dict[str, object] = {
                    "source_field": best_name,
                    "target_field": target_field,
                    "score": round(best_score, 4),
                    "algorithm": settings.FUZZY_ALGORITHM,
                    "candidates": candidates,
                }
                mapping_trace.append(trace_entry)

                if best_score >= settings.FUZZY_THRESHOLD_HIGH:
                    mapped[target_field] = payload[best_original]
                    accepted_scores.append(best_score)
                elif best_score >= settings.FUZZY_THRESHOLD_LOW:
                    mapped[target_field] = payload[best_original]
                    low_confidence_fields.append(target_field)
                    accepted_scores.append(best_score)

        return mapped, mapping_trace, low_confidence_fields, accepted_scores

    def _build_station(self, mapped: Mapping[str, object]) -> NormalizedStation:
        raw_id = self._as_optional_str(mapped.get("raw_id")) or ""
        return NormalizedStation(
            station_id=self._generate_station_id(raw_id),
            name=self._as_optional_str(mapped.get("name")) or "",
            address=self._as_optional_str(mapped.get("address")),
            city=self._as_optional_str(mapped.get("city")),
            province=self._as_optional_str(mapped.get("province")),
            postal_code=self._clean_postal_code(self._as_optional_str(mapped.get("postal_code"))),
            latitude=self._parse_float(mapped.get("latitude")),
            longitude=self._parse_float(mapped.get("longitude")),
            phone=self._clean_phone(self._as_optional_str(mapped.get("phone"))),
            email=self._as_optional_str(mapped.get("email")),
            source_system=self.source_system,
            raw_id=raw_id,
        )

    def _transform_one(self, payload: Mapping[str, object]) -> NormalizedStation | None:
        mapped, mapping_trace, low_confidence_fields, accepted_scores = self._map_payload_fields(payload)

        missing_required = [
            field for field in self._required_fields if not self._as_optional_str(mapped.get(field))
        ]
        if missing_required:
            self._increment_metric("rejected_by_fuzzy_count")
            rejected_payload = dict(payload)
            rejected_payload["mapping_trace"] = mapping_trace
            rejected_payload["missing_required_fields"] = missing_required
            self.record_rejection("fuzzy_mapping_failure", rejected_payload)
            return None

        try:
            station = self._build_station(mapped)
        except Exception:
            self._increment_metric("rejected_by_fuzzy_count")
            rejected_payload = dict(payload)
            rejected_payload["mapping_trace"] = mapping_trace
            self.record_rejection("fuzzy_mapping_failure", rejected_payload)
            return None

        is_valid, validation_reason = self._validate_station(station)
        if not is_valid:
            self._increment_metric("rejected_by_fuzzy_count")
            rejected_payload = dict(payload)
            rejected_payload["mapping_trace"] = mapping_trace
            self.record_rejection(validation_reason or "validation_failed", rejected_payload)
            return None

        if low_confidence_fields:
            low_conf_payload = dict(payload)
            low_conf_payload["mapping_trace"] = mapping_trace
            low_conf_payload["low_confidence_fields"] = low_confidence_fields
            self.record_rejection("fuzzy_low_confidence", low_conf_payload)

        if accepted_scores:
            confidence_sum = float(self.last_metrics.get("_confidence_sum", 0.0)) + sum(
                accepted_scores
            )
            confidence_count = int(self.last_metrics.get("_confidence_count", 0)) + len(accepted_scores)
            self.last_metrics["_confidence_sum"] = confidence_sum
            self.last_metrics["_confidence_count"] = confidence_count

        self._increment_metric("low_confidence_count", len(low_confidence_fields))
        return station

    def transform(self, raw_payload: Any) -> list[NormalizedStation]:
        self.reset_rejections()
        start = perf_counter()
        self.last_metrics = {
            "similarity_compute_ms": 0.0,
            "confidence_mean": 0.0,
            "low_confidence_count": 0,
            "rejected_by_fuzzy_count": 0,
            "_confidence_sum": 0.0,
            "_confidence_count": 0,
        }

        stations_payload: list[Mapping[str, object]]
        if isinstance(raw_payload, dict):
            payload_dict = dict(raw_payload)
            if isinstance(payload_dict.get("stations"), list):
                stations_payload = [
                    station for station in payload_dict["stations"] if isinstance(station, Mapping)
                ]
            elif isinstance(payload_dict.get("estaciones"), list):
                stations_payload = [
                    station for station in payload_dict["estaciones"] if isinstance(station, Mapping)
                ]
            else:
                stations_payload = [payload_dict]
        elif isinstance(raw_payload, list):
            stations_payload = [item for item in raw_payload if isinstance(item, Mapping)]
        else:
            raise ValueError(f"Expected dict or list for fuzzy transformation, got {type(raw_payload)}")

        transformed: list[NormalizedStation] = []
        for station_payload in stations_payload:
            station = self._transform_one(station_payload)
            if station:
                transformed.append(station)

        transformed = self._check_duplicate_within_message(transformed)
        transformed = self._check_duplicate_contact_fields(transformed)

        confidence_sum = float(self.last_metrics.pop("_confidence_sum", 0.0))
        confidence_count = int(self.last_metrics.pop("_confidence_count", 0))
        if confidence_count > 0:
            self.last_metrics["confidence_mean"] = round(confidence_sum / confidence_count, 4)
        else:
            self.last_metrics["confidence_mean"] = 0.0
        self.last_metrics["similarity_compute_ms"] = round((perf_counter() - start) * 1000, 3)

        return transformed
