"""Utilities for splitting incoming payloads into per-station raw messages."""

from __future__ import annotations

import csv
import io
import json
import xml.etree.ElementTree as ET
from typing import Any, Literal


Source = Literal["catalunya", "valencia", "galicia"]
Payload = dict[str, object] | str


def split_payload_by_station(source: Source, data_format: Literal["json", "xml", "csv"], payload: Payload) -> list[Payload]:
    """Split an inbound payload into one raw payload per station.

    The output preserves the original source format expected by transformers.
    """
    if data_format == "json":
        return _split_json_payload(source=source, payload=payload)

    if data_format == "xml":
        if not isinstance(payload, str):
            raise ValueError("XML payload must be a string")
        return _split_xml_payload(payload)

    if data_format == "csv":
        if not isinstance(payload, str):
            raise ValueError("CSV payload must be a string")
        return _split_csv_payload(payload)

    raise ValueError(f"Unsupported format: {data_format}")


def _split_json_payload(source: Source, payload: Payload) -> list[Payload]:
    parsed: Any
    if isinstance(payload, str):
        parsed = json.loads(payload)
    else:
        parsed = payload

    if isinstance(parsed, list):
        station_items = parsed
        return [
            _build_source_json_payload(source=source, station_item=station)
            for station in station_items
            if isinstance(station, dict)
        ]

    if not isinstance(parsed, dict):
        raise ValueError("JSON payload must be an object or an array")

    stations_value = parsed.get("estaciones") if source == "valencia" else parsed.get("stations")
    if isinstance(stations_value, list):
        return [
            _build_source_json_payload(source=source, station_item=station)
            for station in stations_value
            if isinstance(station, dict)
        ]

    if _looks_like_single_station(source=source, item=parsed):
        return [_build_source_json_payload(source=source, station_item=parsed)]

    return []


def _build_source_json_payload(source: Source, station_item: dict[str, object]) -> dict[str, object]:
    if source == "valencia":
        return {"estaciones": [station_item]}
    return {"stations": [station_item]}


def _looks_like_single_station(source: Source, item: dict[str, object]) -> bool:
    if source == "catalunya":
        return "id" in item or "nom" in item
    if source == "valencia":
        return "codigo" in item or "nombre" in item
    return "id" in item or "nome" in item


def _split_xml_payload(payload: str) -> list[str]:
    root = ET.fromstring(payload)
    station_nodes = list(root.findall("station"))
    messages: list[str] = []

    for node in station_nodes:
        container = ET.Element(root.tag, root.attrib)
        container.append(node)
        messages.append(ET.tostring(container, encoding="unicode"))

    return messages


def _split_csv_payload(payload: str) -> list[str]:
    csv_input = io.StringIO(payload.strip())
    reader = csv.reader(csv_input)
    rows = list(reader)
    if len(rows) <= 1:
        return []

    header = rows[0]
    per_row_payloads: list[str] = []
    for row in rows[1:]:
        if not row:
            continue
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(header)
        writer.writerow(row)
        per_row_payloads.append(out.getvalue().strip())

    return per_row_payloads