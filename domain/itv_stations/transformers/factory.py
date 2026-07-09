"""Compatibility wrapper for the transformer factory import path.

Older tooling and fixture scripts import TransformerFactory from
domain.itv_stations.transformers.factory. The actual implementation lives
in apps.normalizer.factory, so this module re-exports it to keep both paths
working.
"""

from __future__ import annotations

from apps.normalizer.factory import TransformerFactory

__all__ = ["TransformerFactory"]