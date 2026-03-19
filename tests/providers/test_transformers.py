from __future__ import annotations

import json
from pathlib import Path

import pytest

from domain.itv_stations.schemas import NormalizedStation
from domain.itv_stations.transformers.catalunya import CatalunyaTransformer
from domain.itv_stations.transformers.galicia import GaliciaTransformer
from domain.itv_stations.transformers.valencia import ValenciaTransformer


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture
def catalunya_xml_payload(fixtures_dir: Path) -> str:
    return (fixtures_dir / "catalunya_sample.xml").read_text(encoding="utf-8")


@pytest.fixture
def galicia_json_payload(fixtures_dir: Path) -> dict[str, object]:
    return json.loads((fixtures_dir / "galicia_sample.json").read_text(encoding="utf-8"))


@pytest.fixture
def valencia_json_payload(fixtures_dir: Path) -> dict[str, object]:
    return json.loads((fixtures_dir / "valencia_sample.json").read_text(encoding="utf-8"))


def _assert_common_normalized_contract(station: NormalizedStation, expected_source: str) -> None:
    assert isinstance(station, NormalizedStation)
    assert station.source_system == expected_source
    assert station.station_id.startswith(expected_source[:3].upper() + "_")
    assert station.name


def test_catalunya_transformer_maps_xml_aliases_to_normalized_schema(
    catalunya_xml_payload: str,
) -> None:
    transformer = CatalunyaTransformer()

    normalized_stations = transformer.transform(catalunya_xml_payload)

    assert len(normalized_stations) == 1
    station = normalized_stations[0]

    _assert_common_normalized_contract(station, expected_source="catalunya")
    assert station.raw_id == "BCN-001"
    assert station.station_id == "CAT_BCN-001"
    assert station.name == "ITV Barcelona Nord"
    assert station.address == "Carrer de la Indústria 123"
    assert station.city == "BARCELONA"
    assert station.province == "BARCELONA"
    assert station.postal_code == "08025"
    assert station.latitude == pytest.approx(41.3851)
    assert station.longitude == pytest.approx(2.1734)
    assert station.phone == "+34932123456"
    assert station.email == "info@itvbarcelona.cat"


def test_galicia_transformer_maps_json_aliases_to_normalized_schema(
    galicia_json_payload: dict[str, object],
) -> None:
    transformer = GaliciaTransformer()

    normalized_stations = transformer.transform(galicia_json_payload)

    assert len(normalized_stations) == 1
    station = normalized_stations[0]

    _assert_common_normalized_contract(station, expected_source="galicia")
    assert station.raw_id == "LU-001"
    assert station.station_id == "GAL_LU-001"
    assert station.name == "ITV Lugo Centro"
    assert station.address == "Rúa da Industria 789"
    assert station.city == "LUGO"
    assert station.province == "LUGO"
    assert station.postal_code == "27001"
    assert station.latitude == pytest.approx(43.0097)
    assert station.longitude == pytest.approx(-7.5567)
    assert station.phone == "+34982123456"
    assert station.email == "info@itvlugo.gal"


def test_valencia_transformer_maps_json_aliases_to_normalized_schema(
    valencia_json_payload: dict[str, object],
) -> None:
    transformer = ValenciaTransformer()

    normalized_stations = transformer.transform(valencia_json_payload)

    assert len(normalized_stations) == 1
    station = normalized_stations[0]

    _assert_common_normalized_contract(station, expected_source="valencia")
    assert station.raw_id == "VAL-042"
    assert station.station_id == "VAL_VAL-042"
    assert station.name == "ITV Valencia Norte"
    assert station.address == "Calle de la Industria 456"
    assert station.city == "VALENCIA"
    assert station.province == "VALENCIA"
    assert station.postal_code == "46015"
    assert station.latitude == pytest.approx(39.4699)
    assert station.longitude == pytest.approx(-0.3763)
    assert station.phone == "+34963456789"
    assert station.email == "contacto@itvvalencia.es"


def test_valencia_transformer_tracks_rejected_items_without_id() -> None:
    transformer = ValenciaTransformer()

    stations = transformer.transform(
        {
            "estaciones": [
                {
                    "nombre": "Sin ID",
                    "direccion": "Calle Falsa 123",
                }
            ]
        }
    )

    assert stations == []
    assert len(transformer.rejected_items) == 1
    assert transformer.rejected_items[0]["reason"] == "missing_raw_id"


def test_galicia_transformer_tracks_rejected_items_without_id() -> None:
    transformer = GaliciaTransformer()

    stations = transformer.transform(
        {
            "stations": [
                {
                    "nome": "Sin ID",
                    "enderezo": "Rúa Falsa 123",
                }
            ]
        }
    )

    assert stations == []
    assert len(transformer.rejected_items) == 1
    assert transformer.rejected_items[0]["reason"] == "missing_raw_id"


def test_catalunya_transformer_tracks_rejected_items_without_id() -> None:
    transformer = CatalunyaTransformer()

    stations = transformer.transform(
        "<stations><station><nom>Sense ID</nom></station></stations>"
    )

    assert stations == []
    assert len(transformer.rejected_items) == 1
    assert transformer.rejected_items[0]["reason"] == "missing_raw_id"
