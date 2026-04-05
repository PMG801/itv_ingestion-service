"""Generate a failure report from `rejected_data.itv_stations`."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping

from aio_pika import connect_robust

from core.config import settings


def _build_amqp_url(
    rabbitmq_url: str | None,
    host: str,
    port: int,
    user: str,
    password: str,
    vhost: str,
) -> str:
    if rabbitmq_url:
        return rabbitmq_url

    normalized_vhost = vhost.lstrip("/")
    return f"amqp://{user}:{password}@{host}:{port}/{normalized_vhost}"


def _as_text(value: object | None, default: str = "unknown") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        normalized = value.strip()
        return normalized or default
    normalized = str(value).strip()
    return normalized or default


def _payload_type_name(value: object | None) -> str:
    if value is None:
        return "none"
    if isinstance(value, dict):
        return "dict"
    if isinstance(value, list):
        return "list"
    if isinstance(value, str):
        return "str"
    return type(value).__name__


def _parse_datetime(value: object | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    if not isinstance(value, str):
        return None

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def classify_reason(reason: str) -> str:
    if reason in {"no_stations_extracted"}:
        return "message_empty"
    if reason in {"station_transform_exception", "schema_validation_failed"}:
        return "processing"
    if reason.startswith("missing_"):
        return "missing_data"
    if reason.startswith("invalid_station_"):
        return "invalid_payload"
    if reason.startswith("invalid_"):
        return "validation"
    if reason.startswith("duplicate_"):
        return "duplicate_detection"
    if reason.startswith("coordinates_") or reason.startswith("postal_code_"):
        return "business_rules"
    if reason == "validation_failed":
        return "validation"
    return "other"


@dataclass(slots=True)
class RejectedDataReport:
    queue_name: str
    total_messages: int = 0
    reason_counts: Counter[str] = field(default_factory=Counter)
    reason_family_counts: Counter[str] = field(default_factory=Counter)
    source_counts: Counter[str] = field(default_factory=Counter)
    format_counts: Counter[str] = field(default_factory=Counter)
    rejection_level_counts: Counter[str] = field(default_factory=Counter)
    raw_payload_type_counts: Counter[str] = field(default_factory=Counter)
    parse_error_counts: Counter[str] = field(default_factory=Counter)
    first_rejected_at: datetime | None = None
    last_rejected_at: datetime | None = None
    sample_by_reason: dict[str, dict[str, Any]] = field(default_factory=dict)

    def add_message(self, message: Mapping[str, Any]) -> None:
        reason = _as_text(message.get("reason"), "unknown_reason")
        source = _as_text(message.get("source"))
        data_format = _as_text(message.get("format"))
        rejection_level = _as_text(message.get("rejection_level"), "unknown")
        raw_payload = message.get("raw_payload", message.get("raw_fragment"))
        rejected_at = _parse_datetime(message.get("rejected_at"))

        self.total_messages += 1
        self.reason_counts[reason] += 1
        self.reason_family_counts[classify_reason(reason)] += 1
        self.source_counts[source] += 1
        self.format_counts[data_format] += 1
        self.rejection_level_counts[rejection_level] += 1
        self.raw_payload_type_counts[_payload_type_name(raw_payload)] += 1

        if rejected_at is not None:
            if self.first_rejected_at is None or rejected_at < self.first_rejected_at:
                self.first_rejected_at = rejected_at
            if self.last_rejected_at is None or rejected_at > self.last_rejected_at:
                self.last_rejected_at = rejected_at

        if reason not in self.sample_by_reason:
            self.sample_by_reason[reason] = {
                "message_id": _as_text(message.get("message_id"), "unknown"),
                "source": source,
                "format": data_format,
                "rejection_level": rejection_level,
                "raw_payload": raw_payload,
                "rejected_at": (
                    rejected_at.isoformat().replace("+00:00", "Z") if rejected_at else None
                ),
            }

    def as_dict(self) -> dict[str, Any]:
        return {
            "queue_name": self.queue_name,
            "total_messages": self.total_messages,
            "reason_counts": dict(self.reason_counts),
            "reason_family_counts": dict(self.reason_family_counts),
            "source_counts": dict(self.source_counts),
            "format_counts": dict(self.format_counts),
            "rejection_level_counts": dict(self.rejection_level_counts),
            "raw_payload_type_counts": dict(self.raw_payload_type_counts),
            "parse_error_counts": dict(self.parse_error_counts),
            "time_window": {
                "first_rejected_at": (
                    self.first_rejected_at.isoformat().replace("+00:00", "Z")
                    if self.first_rejected_at
                    else None
                ),
                "last_rejected_at": (
                    self.last_rejected_at.isoformat().replace("+00:00", "Z")
                    if self.last_rejected_at
                    else None
                ),
            },
            "sample_by_reason": self.sample_by_reason,
        }


def _format_counter(name: str, counter: Counter[str], total: int) -> list[str]:
    lines = [f"{name}:"]
    if not counter:
        lines.append("  - sin datos")
        return lines

    for key, count in counter.most_common():
        percentage = (count / total * 100.0) if total else 0.0
        lines.append(f"  - {key}: {count} ({percentage:.1f}%)")
    return lines


def render_text_report(report: RejectedDataReport) -> str:
    lines = [
        "Informe de rejected_data.itv_stations",
        f"Cola: {report.queue_name}",
        f"Mensajes analizados: {report.total_messages}",
        "",
    ]

    lines.extend(
        _format_counter("Familias de fallo", report.reason_family_counts, report.total_messages)
    )
    lines.append("")
    lines.extend(_format_counter("Motivos exactos", report.reason_counts, report.total_messages))
    lines.append("")
    lines.extend(_format_counter("Origen", report.source_counts, report.total_messages))
    lines.append("")
    lines.extend(_format_counter("Formato", report.format_counts, report.total_messages))
    lines.append("")
    lines.extend(
        _format_counter("Nivel de rechazo", report.rejection_level_counts, report.total_messages)
    )
    lines.append("")
    lines.extend(
        _format_counter(
            "Tipo de payload crudo", report.raw_payload_type_counts, report.total_messages
        )
    )
    lines.append("")

    if report.first_rejected_at or report.last_rejected_at:
        lines.append("Ventana temporal:")
        lines.append(
            f"  - primera: {report.first_rejected_at.isoformat() if report.first_rejected_at else 'n/a'}"
        )
        lines.append(
            f"  - ultima: {report.last_rejected_at.isoformat() if report.last_rejected_at else 'n/a'}"
        )
        lines.append("")

    if report.sample_by_reason:
        lines.append("Muestras por motivo:")
        for reason, sample in report.sample_by_reason.items():
            lines.append(f"  - {reason}: {json.dumps(sample, ensure_ascii=False, default=str)}")

    return "\n".join(lines)


async def collect_rejected_messages(queue_name: str, limit: int = 0) -> RejectedDataReport:
    rabbitmq_url = _build_amqp_url(
        rabbitmq_url=os.getenv("RABBITMQ_URL"),
        host=os.getenv("RABBITMQ_HOST", settings.RABBITMQ_HOST),
        port=int(os.getenv("RABBITMQ_PORT", str(settings.RABBITMQ_PORT))),
        user=os.getenv("RABBITMQ_USER", settings.RABBITMQ_USER),
        password=os.getenv("RABBITMQ_PASS", settings.RABBITMQ_PASS),
        vhost=os.getenv("RABBITMQ_VHOST", settings.RABBITMQ_VHOST),
    )

    try:
        connection = await connect_robust(
            rabbitmq_url,
            timeout=10,
            client_properties={"connection_name": "rejected-data-report"},
        )
    except Exception as exc:
        raise RuntimeError(
            "No se pudo conectar a RabbitMQ. "
            "Pasa una URL/host alcanzable con RABBITMQ_URL o las variables "
            "RABBITMQ_HOST, RABBITMQ_PORT, RABBITMQ_USER, RABBITMQ_PASS y RABBITMQ_VHOST."
        ) from exc

    try:
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=1)
        queue = await channel.declare_queue(queue_name, passive=True, durable=True)

        report = RejectedDataReport(queue_name=queue_name)
        while limit <= 0 or report.total_messages < limit:
            message = await queue.get(no_ack=False, fail=False)
            if message is None:
                break

            try:
                payload = json.loads(message.body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                report.parse_error_counts[type(exc).__name__] += 1
                report.total_messages += 1
                continue

            if not isinstance(payload, dict):
                report.parse_error_counts["non_object_payload"] += 1
                report.total_messages += 1
                continue

            report.add_message(payload)

        return report
    finally:
        await connection.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Lee rejected_data.itv_stations y genera un informe de fallos."
    )
    parser.add_argument(
        "--rabbitmq-url",
        default=None,
        help="URL AMQP completa. Si se indica, tiene prioridad sobre las variables sueltas.",
    )
    parser.add_argument("--rabbitmq-host", default=None, help="Host RabbitMQ.")
    parser.add_argument("--rabbitmq-port", type=int, default=None, help="Puerto RabbitMQ.")
    parser.add_argument("--rabbitmq-user", default=None, help="Usuario RabbitMQ.")
    parser.add_argument("--rabbitmq-pass", default=None, help="Password RabbitMQ.")
    parser.add_argument("--rabbitmq-vhost", default=None, help="Virtual host RabbitMQ.")
    parser.add_argument(
        "--queue",
        default="rejected_data.itv_stations",
        help="Nombre de la cola a analizar.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Numero maximo de mensajes a analizar. 0 = hasta vaciar la cola.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Imprime el informe en JSON en lugar de texto.",
    )
    return parser


async def main_async() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.rabbitmq_url is not None:
        os.environ["RABBITMQ_URL"] = args.rabbitmq_url
    if args.rabbitmq_host is not None:
        os.environ["RABBITMQ_HOST"] = args.rabbitmq_host
    if args.rabbitmq_port is not None:
        os.environ["RABBITMQ_PORT"] = str(args.rabbitmq_port)
    if args.rabbitmq_user is not None:
        os.environ["RABBITMQ_USER"] = args.rabbitmq_user
    if args.rabbitmq_pass is not None:
        os.environ["RABBITMQ_PASS"] = args.rabbitmq_pass
    if args.rabbitmq_vhost is not None:
        os.environ["RABBITMQ_VHOST"] = args.rabbitmq_vhost

    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    try:
        report = await collect_rejected_messages(args.queue, args.limit)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(report.as_dict(), indent=2, ensure_ascii=False, default=str))
    else:
        print(render_text_report(report))

    return 0


def main() -> None:
    raise SystemExit(asyncio.run(main_async()))


if __name__ == "__main__":
    main()
