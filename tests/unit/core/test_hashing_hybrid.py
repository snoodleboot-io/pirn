"""Hybrid A+B canonicalisation hooks for ``content_hash``.

These tests pin the two extension points that unblock content-hashing of
rich domain dataclasses (``DataBatch`` / ``DataSchema``):

* Hook A — ``__pirn_canonical__()`` is consulted before the
  ``BaseModel`` branch so a type can declare its canonical form
  explicitly.
* Fallback B — types declaring ``__get_pydantic_core_schema__`` (i.e.
  pydantic-aware non-``BaseModel`` types like the frozen dataclasses
  that subclass :class:`PirnOpaqueValue`) are hashed via
  :class:`pydantic.TypeAdapter` instead of raising ``_Unhashable``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.hashing import content_hash
from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class _CanonicalHookFirst:
    """Plain dataclass exposing only ``__pirn_canonical__``.

    Has no ``__get_pydantic_core_schema__`` and is not a
    :class:`pydantic.BaseModel`, so the canonical hook is the only
    branch that can rescue it from ``_Unhashable``.
    """

    name: str
    weight: int

    def __pirn_canonical__(self) -> dict[str, Any]:
        return {"n": self.name, "w": self.weight}


@dataclass(frozen=True)
class _PydanticAwareOnly(PirnOpaqueValue):
    """Frozen-dataclass opaque value: pydantic schema, no canonical hook.

    :class:`PirnOpaqueValue` adds ``__get_pydantic_core_schema__`` via
    its mixin; without ``__pirn_canonical__`` the hasher must take the
    pydantic ``TypeAdapter`` fallback path.
    """

    label: str = ""
    payload: tuple[int, ...] = ()

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {"label": self.label, "payload": list(self.payload)}


@dataclass(frozen=True)
class _BothHooks(PirnOpaqueValue):
    """Has both hooks; the canonical hook must win."""

    label: str = ""

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {"audit": self.label}

    def __pirn_canonical__(self) -> dict[str, Any]:
        return {"canonical": self.label}


class TestCanonicalHook:
    """Hook A — ``__pirn_canonical__`` runs before the ``BaseModel`` branch."""

    def test_hook_drives_hash(self) -> None:
        a = _CanonicalHookFirst(name="alice", weight=3)
        b = _CanonicalHookFirst(name="alice", weight=3)
        c = _CanonicalHookFirst(name="alice", weight=4)
        assert content_hash(a) == content_hash(b)
        assert content_hash(a) != content_hash(c)

    def test_hash_matches_hooks_primitive_form(self) -> None:
        a = _CanonicalHookFirst(name="alice", weight=3)
        assert content_hash(a) == content_hash({"n": "alice", "w": 3})

    def test_hook_takes_precedence_over_pydantic_schema(self) -> None:
        # _BothHooks subclasses PirnOpaqueValue (so it has a pydantic
        # core schema) AND defines __pirn_canonical__. The canonical
        # hook must be consulted first.
        a = _BothHooks(label="hello")
        assert content_hash(a) == content_hash({"canonical": "hello"})
        assert content_hash(a) != content_hash({"audit": "hello"})


class TestPydanticAwareFallback:
    """Fallback B — ``__get_pydantic_core_schema__`` rescues opaque values."""

    def test_fallback_avoids_unhashable_marker(self) -> None:
        a = _PydanticAwareOnly(label="x", payload=(1, 2, 3))
        h = content_hash(a)
        assert "unhashable" not in h
        assert h.startswith("sha256:")
        # 7 chars for the "sha256:" prefix + 64 hex chars of digest.
        assert len(h) == 7 + 64

    def test_fallback_is_stable(self) -> None:
        a = _PydanticAwareOnly(label="x", payload=(1, 2, 3))
        b = _PydanticAwareOnly(label="x", payload=(1, 2, 3))
        c = _PydanticAwareOnly(label="x", payload=(1, 2, 4))
        assert content_hash(a) == content_hash(b)
        assert content_hash(a) != content_hash(c)


class TestDataBatchEndToEnd:
    """End-to-end sanity: a real :class:`DataBatch` flows through cleanly."""

    def test_data_batch_hash_equals_canonical_form(self) -> None:
        from pirn.domains.data.data_batch import DataBatch
        from pirn.domains.data.data_schema import DataSchema

        schema = DataSchema(
            columns={"id": int, "name": str},
            primary_keys=("id",),
        )
        rows = ({"id": 1, "name": "a"}, {"id": 2, "name": "b"})
        batch = DataBatch(
            rows=rows, schema=schema, source_uri="memory://t"
        )
        # Canonical form is what __pirn_canonical__ returns; the hasher
        # must produce the same digest as hashing that primitive dict
        # directly.
        canonical_form = batch.__pirn_canonical__()
        assert content_hash(batch) == content_hash(canonical_form)
        # And the digest is a proper sha256, not the unhashable marker.
        assert "unhashable" not in content_hash(batch)
