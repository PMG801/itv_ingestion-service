from __future__ import annotations

import pytest

from apps.normalizer.factory import TransformerFactory
from core.config import settings
from domain.itv_stations.transformers.base import BaseTransformer
from domain.itv_stations.transformers.catalunya import CatalunyaTransformer
from domain.itv_stations.transformers.fuzzy import FuzzyTransformer


class DummyTransformer(BaseTransformer):
    def __init__(self) -> None:
        super().__init__(source_system="dummy")

    def transform(self, raw_payload: object):
        return []


@pytest.fixture(autouse=True)
def restore_transformer_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    original = TransformerFactory._transformers.copy()
    monkeypatch.setattr(settings, "NORMALIZATION_MODE", "RULES")
    try:
        yield
    finally:
        TransformerFactory._transformers = original


def test_factory_creates_supported_transformer() -> None:
    transformer = TransformerFactory.create(" Catalunya ")

    assert isinstance(transformer, CatalunyaTransformer)


def test_factory_rejects_unsupported_source() -> None:
    with pytest.raises(ValueError, match="Unsupported source system"):
        TransformerFactory.create("madrid")


def test_factory_registers_new_transformer_and_marks_it_supported() -> None:
    TransformerFactory.register_transformer("madrid", DummyTransformer)

    assert TransformerFactory.is_supported(" MADRID ") is True
    assert isinstance(TransformerFactory.create("madrid"), DummyTransformer)


def test_factory_rejects_invalid_transformer_type() -> None:
    with pytest.raises(TypeError, match="must inherit from BaseTransformer"):
        TransformerFactory.register_transformer("broken", str)


def test_factory_supported_sources_returns_list() -> None:
    """Test that supported_sources returns list of available sources."""
    sources = TransformerFactory.supported_sources()

    assert isinstance(sources, list)
    assert "catalunya" in sources
    assert "valencia" in sources
    assert "galicia" in sources


def test_factory_is_supported_with_valid_source() -> None:
    """Test that is_supported returns True for valid sources."""
    assert TransformerFactory.is_supported("catalunya") is True
    assert TransformerFactory.is_supported("valencia") is True
    assert TransformerFactory.is_supported("galicia") is True


def test_factory_is_supported_with_invalid_source() -> None:
    """Test that is_supported returns False for invalid sources."""
    assert TransformerFactory.is_supported("invalid") is False


def test_factory_is_supported_case_insensitive() -> None:
    """Test that is_supported is case-insensitive."""
    assert TransformerFactory.is_supported("CATALUNYA") is True
    assert TransformerFactory.is_supported("Valencia") is True
    assert TransformerFactory.is_supported(" galicia ") is True


def test_factory_create_all_sources() -> None:
    """Test that factory can create transformers for all supported sources."""
    for source in TransformerFactory.supported_sources():
        transformer = TransformerFactory.create(source)
        assert isinstance(transformer, BaseTransformer)
        assert transformer.source_system == source


def test_factory_creates_fuzzy_transformer_when_mode_is_fuzzy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "NORMALIZATION_MODE", "FUZZY")

    transformer = TransformerFactory.create("unsupported-source")

    assert isinstance(transformer, FuzzyTransformer)


def test_factory_rejects_invalid_normalization_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "NORMALIZATION_MODE", "BROKEN")

    with pytest.raises(ValueError, match="Unsupported normalization mode"):
        TransformerFactory.create("catalunya")
