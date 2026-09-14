"""Performance-related invariants for :meth:`ContentHasher.hash`.

These tests don't measure wall-clock — they assert structural properties
that the optimisations rely on (e.g. TypeAdapter caching).
"""

from __future__ import annotations

import unittest
from dataclasses import dataclass

from pydantic import BaseModel

from pirn.core.content_hasher import ContentHasher
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
        ContentHasher._type_adapter_cache.clear()
        a = _OpaqueValue(name="a", count=1)
        b = _OpaqueValue(name="b", count=2)

        h1 = ContentHasher.hash(a)
        h2 = ContentHasher.hash(b)
        assert h1 != h2
        # Only one cached adapter for ``_OpaqueValue`` regardless of call count.
        cached_types = {t for t in ContentHasher._type_adapter_cache.keys()}
        assert _OpaqueValue in cached_types
        assert len(cached_types) == 1

        # Calling again does not re-cache.
        ContentHasher.hash(a)
        ContentHasher.hash(b)
        assert len(ContentHasher._type_adapter_cache) == 1

    def test_primitives_skip_type_adapter_cache(self) -> None:
        """Primitives must not populate the TypeAdapter cache (no schema lookup)."""
        ContentHasher._type_adapter_cache.clear()
        ContentHasher.hash(42)
        ContentHasher.hash("hello")
        ContentHasher.hash(None)
        ContentHasher.hash(True)
        ContentHasher.hash(b"bytes")
        assert ContentHasher._type_adapter_cache == {}

    def test_pydantic_basemodel_skips_type_adapter_cache(self) -> None:
        """``BaseModel`` instances use ``model_dump`` directly — no TypeAdapter."""
        ContentHasher._type_adapter_cache.clear()
        ContentHasher.hash(_PlainModel(x=1, y="a"))
        assert ContentHasher._type_adapter_cache == {}
