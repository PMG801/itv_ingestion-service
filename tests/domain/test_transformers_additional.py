"""Additional tests for domain transformers to improve coverage."""

from __future__ import annotations

import pytest

from domain.itv_stations.transformers.base import BaseTransformer
from domain.itv_stations.transformers.catalunya import CatalunyaTransformer
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
