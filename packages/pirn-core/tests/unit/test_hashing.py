"""Content-addressed hashing tests."""

from __future__ import annotations

# cross-domain: skipped in per-package isolation, run by the unified suite (SCD-24)
import pytest as _pytest

_pytest.importorskip("pirn_data")
pytestmark = _pytest.mark.cross_domain

import unittest
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from pirn.core.content_hasher import ContentHasher
from pirn.core.pirn_opaque_value import PirnOpaqueValue


class _StandaloneTests(unittest.TestCase):
    def test_primitives_stable(self):
        assert ContentHasher.hash(5) == ContentHasher.hash(5)
        assert ContentHasher.hash("hello") == ContentHasher.hash("hello")
        assert ContentHasher.hash(None) == ContentHasher.hash(None)
        assert ContentHasher.hash(True) == ContentHasher.hash(True)

    def test_primitives_distinct(self):
        assert ContentHasher.hash(5) != ContentHasher.hash(5.0) or ContentHasher.hash(
            5
        ) != ContentHasher.hash("5")
        assert ContentHasher.hash(True) != ContentHasher.hash(1)
        assert ContentHasher.hash(None) != ContentHasher.hash(0)

    def test_dict_ordering_doesnt_matter(self):
        a = {"x": 1, "y": 2}
        b = {"y": 2, "x": 1}
        assert ContentHasher.hash(a) == ContentHasher.hash(b)

    def test_list_ordering_matters(self):
        assert ContentHasher.hash([1, 2, 3]) != ContentHasher.hash([3, 2, 1])

    def test_set_ordering_doesnt_matter(self):
        assert ContentHasher.hash({1, 2, 3}) == ContentHasher.hash({3, 2, 1})

    def test_pydantic_model_stable(self):
        class M(BaseModel):
            x: int
            y: str

        assert ContentHasher.hash(M(x=1, y="a")) == ContentHasher.hash(M(x=1, y="a"))
        assert ContentHasher.hash(M(x=1, y="a")) != ContentHasher.hash(M(x=2, y="a"))

    def test_bytes_stable(self):
        assert ContentHasher.hash(b"hello") == ContentHasher.hash(b"hello")
        assert ContentHasher.hash(b"hello") != ContentHasher.hash("hello")

    def test_nested_structures(self):
        a = {"users": [{"id": 1, "name": "alice"}, {"id": 2, "name": "bob"}]}
        b = {"users": [{"name": "alice", "id": 1}, {"id": 2, "name": "bob"}]}
        assert ContentHasher.hash(a) == ContentHasher.hash(b)

    def test_hash_format(self):
        h = ContentHasher.hash(42)
        assert h.startswith("sha256:")
        assert len(h) == 7 + 64  # "sha256:" + 64 hex chars

    def test_unhashable_returns_marker(self):
        class Opaque:
            pass

        h = ContentHasher.hash(Opaque())
        assert "unhashable" in h


# ---------------------------------------------------------------------------
# Hybrid A+B canonicalisation hooks
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _CanonicalHookOnly:
    """Dataclass exposing only the sanctioned ``__pirn_canonical__`` hook."""

    name: str
    weight: int

    def __pirn_canonical__(self) -> dict[str, Any]:
        return {"n": self.name, "w": self.weight}


@dataclass(frozen=True)
class _SchemaOnly(PirnOpaqueValue):
    """Frozen-dataclass opaque value: pydantic schema, no canonical hook."""

    label: str = ""
    payload: tuple[int, ...] = ()

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {"label": self.label, "payload": list(self.payload)}


@dataclass(frozen=True)
class _BothHooks(PirnOpaqueValue):
    """Has both hooks; canonical hook must win."""

    label: str = ""

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {"audit": self.label}

    def __pirn_canonical__(self) -> dict[str, Any]:
        return {"canonical": self.label}

    def test_canonical_hook_drives_hash(self):
        a = _CanonicalHookOnly(name="alice", weight=3)
        b = _CanonicalHookOnly(name="alice", weight=3)
        c = _CanonicalHookOnly(name="alice", weight=4)
        # Two structurally identical hook outputs hash identically.
        assert ContentHasher.hash(a) == ContentHasher.hash(b)
        # A different field value reaches the hash via the hook.
        assert ContentHasher.hash(a) != ContentHasher.hash(c)
        # The hash must equal what we'd get hashing the hook's primitive form.
        assert ContentHasher.hash(a) == ContentHasher.hash({"n": "alice", "w": 3})

    def test_pydantic_schema_fallback_avoids_unhashable_marker(self):
        a = _SchemaOnly(label="x", payload=(1, 2, 3))
        h = ContentHasher.hash(a)
        # The previous behaviour was the unhashable marker — the new branch
        # must produce a real sha256 digest derived from the dump.
        assert "unhashable" not in h
        assert h.startswith("sha256:")
        assert len(h) == 7 + 64
        # And it should match hashing the primitive dump directly.
        assert ContentHasher.hash(a) == ContentHasher.hash({"label": "x", "payload": [1, 2, 3]})

    def test_canonical_hook_takes_precedence_over_pydantic_schema(self):
        a = _BothHooks(label="hello")
        # Hook output, not audit_dict output, must drive the hash.
        assert ContentHasher.hash(a) == ContentHasher.hash({"canonical": "hello"})
        assert ContentHasher.hash(a) != ContentHasher.hash({"audit": "hello"})

    def test_data_batch_content_hash_stable(self):
        """End-to-end: a real DataBatch with type-bearing schema hashes cleanly."""
        from pirn_data.data_batch import DataBatch
        from pirn_data.data_schema import DataSchema

        schema = DataSchema(
            columns={"id": int, "name": str},
            primary_keys=("id",),
        )
        rows = ({"id": 1, "name": "a"}, {"id": 2, "name": "b"})
        fixed_uri = "memory://t"
        a = DataBatch(rows=rows, schema=schema, source_uri=fixed_uri)
        b = DataBatch(rows=rows, schema=schema, source_uri=fixed_uri)
        # ``fetched_at`` is per-instance — the hashes are equal only when
        # both share the same materialisation timestamp.
        object.__setattr__(b, "fetched_at", a.fetched_at)
        h_a = ContentHasher.hash(a)
        assert "unhashable" not in h_a
        assert h_a.startswith("sha256:")
        assert h_a == ContentHasher.hash(b)
