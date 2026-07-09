"""Evaluate LLMTransformer semantic mapping on source fixtures.

This script runs a controlled experiment over fixture samples and exports a JSON report with:
- source
- time_ms
- valid (bool)
- peak_memory_bytes

It uses micro-batches to reduce token/latency overhead while preserving sequential execution.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import tracemalloc
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter, sleep
from typing import Any

from domain.itv_stations.transformers.llm_transformer import LLMTransformer


@dataclass(slots=True)
class EvalRow:
    source: str
    record_index: int
    time_ms: float
    valid: bool
    peak_memory_bytes: int


def _load_fixture_payload(source: str) -> Any:
    fixtures_dir = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
    if source == "catalunya":
        return (fixtures_dir / "catalunya_sample.xml").read_text(encoding="utf-8")

    if source == "valencia":
        return json.loads((fixtures_dir / "valencia_sample.json").read_text(encoding="utf-8"))

    if source == "galicia":
        return json.loads((fixtures_dir / "galicia_sample.json").read_text(encoding="utf-8"))

    raise ValueError(f"Unsupported source: {source}")


def _extract_records(source: str, fixture_payload: Any) -> list[Any]:
    if source == "catalunya":
        # Catalunya fixture is XML with one station; duplicate for experiment cardinality.
        return [fixture_payload]

    if isinstance(fixture_payload, dict):
        stations = fixture_payload.get("stations")
        if isinstance(stations, list) and stations:
            return stations

        estaciones = fixture_payload.get("estaciones")
        if isinstance(estaciones, list) and estaciones:
            return estaciones

        return [fixture_payload]

    if isinstance(fixture_payload, list) and fixture_payload:
        return fixture_payload

    return [fixture_payload]


def _select_n_records(base_records: list[Any], n: int) -> list[Any]:
    if not base_records:
        return []
    selected: list[Any] = []
    for i in range(n):
        selected.append(base_records[i % len(base_records)])
    return selected


async def _evaluate_source(source: str, records: list[Any], batch_size: int) -> list[EvalRow]:
    transformer = LLMTransformer(source_system=source)
    output_rows: list[EvalRow] = []

    record_cursor = 0
    for batch_idx, batch_start in enumerate(range(0, len(records), batch_size)):
        batch = records[batch_start : batch_start + batch_size]

        tracemalloc.start()
        started = perf_counter()
        stations = await transformer.transform_batch_async(batch)
        elapsed_ms = (perf_counter() - started) * 1000
        _, peak_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        # If counts mismatch, mark remaining inputs as invalid.
        valid_count = min(len(stations), len(batch))
        for index_in_batch in range(len(batch)):
            is_valid = index_in_batch < valid_count
            output_rows.append(
                EvalRow(
                    source=source,
                    record_index=record_cursor,
                    time_ms=round(elapsed_ms / max(len(batch), 1), 3),
                    valid=is_valid,
                    peak_memory_bytes=peak_mem,
                )
            )
            record_cursor += 1

        # Delay between batches to avoid Groq rate limits (tokens/min)
        if batch_idx < (len(records) - 1) // batch_size:
            sleep(3.0)

    return output_rows


async def run_experiment(samples_per_source: int, batch_size: int) -> dict[str, Any]:
    sources = ["catalunya", "valencia", "galicia"]
    all_rows: list[EvalRow] = []

    for source in sources:
        fixture_payload = _load_fixture_payload(source)
        base_records = _extract_records(source, fixture_payload)
        selected_records = _select_n_records(base_records, samples_per_source)
        rows = await _evaluate_source(source, selected_records, batch_size)
        all_rows.extend(rows)

    total_valid = sum(1 for row in all_rows if row.valid)
    total_rows = len(all_rows)
    return {
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "samples_per_source": samples_per_source,
        "batch_size": batch_size,
        "total_records": total_rows,
        "total_valid": total_valid,
        "valid_ratio": round(total_valid / total_rows, 4) if total_rows else 0.0,
        "rows": [asdict(row) for row in all_rows],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate LLMTransformer over fixtures")
    parser.add_argument("--samples-per-source", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=5)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("scripts") / "llm_transformer_eval_results.json",
    )
    args = parser.parse_args()

    report = asyncio.run(run_experiment(args.samples_per_source, args.batch_size))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Report written to {args.output}")
    print(f"Records: {report['total_records']} | Valid: {report['total_valid']}")


if __name__ == "__main__":
    main()
