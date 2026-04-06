from __future__ import annotations

from apps.gateway.fanout import split_payload_by_station


def test_split_json_payload_by_station_for_valencia() -> None:
    payload = {
        "estaciones": [
            {"codigo": "VAL-001", "nombre": "A"},
            {"codigo": "VAL-002", "nombre": "B"},
        ]
    }

    messages = split_payload_by_station(source="valencia", data_format="json", payload=payload)

    assert len(messages) == 2
    assert messages[0] == {"estaciones": [{"codigo": "VAL-001", "nombre": "A"}]}
    assert messages[1] == {"estaciones": [{"codigo": "VAL-002", "nombre": "B"}]}


def test_split_xml_payload_by_station() -> None:
    payload = (
        "<stations>"
        "<station><id>CAT-001</id></station>"
        "<station><id>CAT-002</id></station>"
        "</stations>"
    )

    messages = split_payload_by_station(source="catalunya", data_format="xml", payload=payload)

    assert len(messages) == 2
    assert "CAT-001" in messages[0]
    assert "CAT-002" in messages[1]


def test_split_csv_payload_by_station() -> None:
    payload = "id,nome\nGAL-001,ITV A\nGAL-002,ITV B\n"

    messages = split_payload_by_station(source="galicia", data_format="csv", payload=payload)

    assert len(messages) == 2
    assert messages[0] == "id,nome\r\nGAL-001,ITV A"
    assert messages[1] == "id,nome\r\nGAL-002,ITV B"
