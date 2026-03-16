from __future__ import annotations

import pytest

from apps.normalizer.factory import TransformerFactory
from domain.itv_stations.transformers.base import BaseTransformer
from domain.itv_stations.transformers.catalunya import CatalunyaTransformer


class DummyTransformer(BaseTransformer):
    def __init__(self) -> None:
        super().__init__(source_system="dummy")

    def transform(self, raw_payload: object):
        return []


@pytest.fixture(autouse=True)
def restore_transformer_registry() -> None:
    original = TransformerFactory._transformers.copy()
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