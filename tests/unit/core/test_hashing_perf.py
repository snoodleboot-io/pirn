"""Performance-related invariants for :func:`content_hash`.

These tests don't measure wall-clock — they assert structural properties
that the optimisations rely on (e.g. TypeAdapter caching).
"""

from __future__ import annotations

from dataclasses import dataclass
import unittest

from pydantic import BaseModel

from pirn.core import hashing
from pirn.core.hashing import content_hash
from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class _OpaqueValue(PirnOpaqueValue):
    """Frozen dataclass leveraging the PirnOpaqueValue Pydantic shim."""

    name: str
    count: int


class _PlainModel(BaseModel):
    x: int
    y: str



class _StandaloneTests(unittest.TestCase):
    def test_type_adapter_is_cached_per_type(self) -> None:
        """Repeated canonicalisation of the same opaque type reuses one TypeAdapter."""
        hashing._type_adapter_cache.clear()
        a = _OpaqueValue(name="a", count=1)
        b = _OpaqueValue(name="b", count=2)
    
        h1 = content_hash(a)
        h2 = content_hash(b)
        assert h1 != h2
        # Only one cached adapter for ``_OpaqueValue`` regardless of call count.
        cached_types = {t for t in hashing._type_adapter_cache.keys()}
        assert _OpaqueValue in cached_types
        assert len(cached_types) == 1
    
        # Calling again does not re-cache.
        content_hash(a)
        content_hash(b)
        assert len(hashing._type_adapter_cache) == 1
    
    
    def test_primitives_skip_type_adapter_cache(self) -> None:
        """Primitives must not populate the TypeAdapter cache (no schema lookup)."""
        hashing._type_adapter_cache.clear()
        content_hash(42)
        content_hash("hello")
        content_hash(None)
        content_hash(True)
        content_hash(b"bytes")
        assert hashing._type_adapter_cache == {}
    
    
    def test_pydantic_basemodel_skips_type_adapter_cache(self) -> None:
        """``BaseModel`` instances use ``model_dump`` directly — no TypeAdapter."""
        hashing._type_adapter_cache.clear()
        content_hash(_PlainModel(x=1, y="a"))
        assert hashing._type_adapter_cache == {}
