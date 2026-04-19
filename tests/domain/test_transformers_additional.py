"""Additional tests for domain transformers to improve coverage."""

from __future__ import annotations

import pytest

from domain.itv_stations.transformers.base import BaseTransformer
from domain.itv_stations.transformers.catalunya import CatalunyaTransformer
from domain.itv_stations.transformers.fuzzy import FuzzyTransformer
from domain.itv_stations.transformers.galicia import GaliciaTransformer
from domain.itv_stations.transformers.valencia import ValenciaTransformer


def test_transformer_initialization() -> None:
    """Test that transformer initializes properly."""
    transformer = CatalunyaTransformer()
    assert transformer.source_system == "catalunya"
    assert isinstance(transformer.rejected_items, list)


def test_record_rejection_dict_fragment() -> None:
    """Test recording rejection with dict fragment."""
    transformer = CatalunyaTransformer()
    transformer.record_rejection("test_reason", {"key": "value"})
    assert len(transformer.rejected_items) == 1


def test_record_rejection_string_fragment() -> None:
    """Test recording rejection with string fragment."""
    transformer = ValenciaTransformer()
    transformer.record_rejection("parse_error", "raw_xml_string")
    assert len(transformer.rejected_items) == 1


def test_record_rejection_none_fragment() -> None:
    """Test recording rejection with None fragment."""
    transformer = GaliciaTransformer()
    transformer.record_rejection("unknown_error", None)
    assert len(transformer.rejected_items) == 1


def test_reset_rejections_clears_list() -> None:
    """Test that reset_rejections clears the rejected items list."""
    transformer = CatalunyaTransformer()

    # Add some rejections
    for i in range(5):
        transformer.record_rejection(f"reason_{i}", f"fragment_{i}")
    assert len(transformer.rejected_items) == 5

    # Reset
    transformer.reset_rejections()
    assert len(transformer.rejected_items) == 0


def test_multiple_rejections_accumulate() -> None:
    """Test that multiple rejections accumulate."""
    transformer = ValenciaTransformer()

    for i in range(10):
        transformer.record_rejection(f"reason_{i}", f"data_{i}")

    assert len(transformer.rejected_items) == 10


def test_all_transformers_have_correct_source_system() -> None:
    """Test all transformers have correct source_system attribute."""
    cat = CatalunyaTransformer()
    gal = GaliciaTransformer()
    val = ValenciaTransformer()

    assert cat.source_system == "catalunya"
    assert gal.source_system == "galicia"
    assert val.source_system == "valencia"


def test_transformer_isinstance_base_transformer() -> None:
    """Test that all transformers are instances of BaseTransformer."""
    cat = CatalunyaTransformer()
    gal = GaliciaTransformer()
    val = ValenciaTransformer()

    assert isinstance(cat, BaseTransformer)
    assert isinstance(gal, BaseTransformer)
    assert isinstance(val, BaseTransformer)


def test_transformer_has_transform_method() -> None:
    """Test that transformers have transform method."""
    cat = CatalunyaTransformer()
    assert hasattr(cat, "transform")
    assert callable(cat.transform)


def test_transformer_rejection_with_empty_string_reason() -> None:
    """Test rejection with empty string reason."""
    transformer = ValenciaTransformer()
    transformer.record_rejection("", "fragment")
    assert len(transformer.rejected_items) == 1


def test_transformer_multiple_resets() -> None:
    """Test multiple resets don't cause errors."""
    transformer = GaliciaTransformer()

    for _ in range(3):
        transformer.record_rejection("reason", "data")
        transformer.reset_rejections()
        assert len(transformer.rejected_items) == 0


def test_rejected_items_structure() -> None:
    """Test that rejected_items has correct structure."""
    transformer = CatalunyaTransformer()
    transformer.record_rejection("test_reason", {"key": "value"})

    assert len(transformer.rejected_items) == 1
    item = transformer.rejected_items[0]
    assert "reason" in item
    assert item["reason"] == "test_reason"
    assert "raw_fragment" in item


def test_fuzzy_transformer_maps_catalunya_aliases() -> None:
    transformer = FuzzyTransformer(source_system="catalunya")
    payload = {
        "stations": [
            {
                "id": "BCN-001",
                "nom": "  ITV Barcelona Nord  ",
                "adreca": "Carrer de la Indústria 123",
                "ciutat": "Barcelona",
                "provincia": "Barcelona",
                "codi_postal": "08025",
                "latitud": "41,3851",
                "longitud": "2,1734",
                "telefon": "932 123 456",
                "email": "info@itvbarcelona.cat",
            }
        ]
    }

    stations = transformer.transform(payload)

    assert len(stations) == 1
    station = stations[0]
    assert station.raw_id == "BCN-001"
    assert station.name == "ITV Barcelona Nord"
    assert station.city == "BARCELONA"
    assert station.phone == "+34932123456"
    assert station.email == "info@itvbarcelona.cat"
    assert int(transformer.last_metrics["rejected_by_fuzzy_count"]) == 0


def test_fuzzy_transformer_maps_galicia_aliases() -> None:
    transformer = FuzzyTransformer(source_system="galicia")
    payload = {
        "stations": [
            {
                "id": "LU-001",
                "nome": "  ITV Lugo Centro  ",
                "enderezo": "Rúa da Industria 789",
                "concello": "Lugo",
                "provincia": "Lugo",
                "cp": "27001",
                "lat": 43.0097,
                "lon": -7.5567,
                "telefono": "982 123 456",
                "correo": "info@itvlugo.gal",
            }
        ]
    }

    stations = transformer.transform(payload)

    assert len(stations) == 1
    station = stations[0]
    assert station.raw_id == "LU-001"
    assert station.name == "ITV Lugo Centro"
    assert station.postal_code == "27001"
    assert station.latitude == pytest.approx(43.0097)
    assert station.longitude == pytest.approx(-7.5567)
    assert int(transformer.last_metrics["rejected_by_fuzzy_count"]) == 0


def test_fuzzy_transformer_maps_valencia_aliases() -> None:
    transformer = FuzzyTransformer(source_system="valencia")
    payload = {
        "estaciones": [
            {
                "codigo": "VAL-042",
                "nombre": "  ITV Valencia Norte  ",
                "direccion": "Calle de la Industria 456",
                "poblacion": "Valencia",
                "provincia": "Valencia",
                "codigo_postal": "46015",
                "latitud": 39.4699,
                "longitud": -0.3763,
                "telefono": "963 456 789",
                "correo": "contacto@itvvalencia.es",
            }
        ]
    }

    stations = transformer.transform(payload)

    assert len(stations) == 1
    station = stations[0]
    assert station.raw_id == "VAL-042"
    assert station.name == "ITV Valencia Norte"
    assert station.province == "VALENCIA"
    assert station.station_id == "VAL_VAL-042"
    assert int(transformer.last_metrics["rejected_by_fuzzy_count"]) == 0


def test_fuzzy_transformer_accepts_xml_payload() -> None:
        transformer = FuzzyTransformer(source_system="catalunya")
        payload = """<stations>
    <station>
        <id>BCN-009</id>
        <nom>ITV Barcelona Sants</nom>
        <adreca>Carrer de Sants 99</adreca>
        <ciutat>Barcelona</ciutat>
        <provincia>Barcelona</provincia>
        <codi_postal>08014</codi_postal>
        <latitud>41.3760</latitud>
        <longitud>2.1360</longitud>
        <telefon>932 999 888</telefon>
        <email>info@itvsants.cat</email>
    </station>
</stations>"""

        stations = transformer.transform(payload)

        assert len(stations) == 1
        station = stations[0]
        assert station.raw_id == "BCN-009"
        assert station.name == "ITV Barcelona Sants"
        assert station.province == "BARCELONA"
        assert int(transformer.last_metrics["rejected_by_fuzzy_count"]) == 0


def test_fuzzy_transformer_accepts_csv_payload() -> None:
        transformer = FuzzyTransformer(source_system="galicia")
        payload = """id,nome,enderezo,concello,provincia,cp,lat,lon,telefono,email
LU-009,ITV Lugo Sur,Rúa da Industria 9,Lugo,Lugo,27001,43.0097,-7.5567,982123999,info@itvlugosur.gal"""

        stations = transformer.transform(payload)

        assert len(stations) == 1
        station = stations[0]
        assert station.raw_id == "LU-009"
        assert station.name == "ITV Lugo Sur"
        assert station.postal_code == "27001"
        assert int(transformer.last_metrics["rejected_by_fuzzy_count"]) == 0
