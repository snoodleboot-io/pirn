"""``MemoryRecord`` — one typed, provenance-carrying unit of agent memory.

The single value object every F27 memory-management piece reads and writes. It
pairs the record's :data:`~pirn_agents.memory_management.memory_kind.MemoryKind`
(episodic/semantic/procedural/profile) and text ``content`` with a
:class:`~pirn_agents.memory_management.memory_provenance.MemoryProvenance` and two
lifecycle signals used by decay and ranking: ``importance`` and ``last_accessed``.

It round-trips through the untyped
:class:`~pirn_agents.memory_store.MemoryStore` mapping interface via
:meth:`to_payload` / :meth:`from_payload`, so existing ``memory_patterns/`` stores
keep reading and writing plain mappings while callers gain a typed, validated
view — the S5 migration path that leaves the store interface unchanged.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.memory_management.memory_kind import MemoryKind, is_memory_kind
from pirn_agents.memory_management.memory_provenance import MemoryProvenance


@dataclass(frozen=True)
class MemoryRecord(PirnOpaqueValue):
    """A frozen, typed memory record with provenance and lifecycle signals.

    Attributes
    ----------
    id:
        Stable primary key; the store key the record is persisted under.
    kind:
        The record's :data:`MemoryKind`.
    content:
        The record's text payload.
    provenance:
        Origin + trust metadata.
    created_at:
        Timezone-aware creation time; the recency anchor when ``last_accessed``
        is unset.
    importance:
        Caller-assigned importance in ``[0.0, 1.0]``; higher survives decay and
        ranks higher. Defaults to neutral ``0.0``.
    last_accessed:
        Timezone-aware last-read time, or ``None`` if never re-accessed.
    metadata:
        Arbitrary scalar metadata (e.g. ``session_id``, subject keys).
    """

    id: str
    kind: MemoryKind
    content: str
    provenance: MemoryProvenance
    created_at: datetime
    importance: float = 0.0
    last_accessed: datetime | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id:
            raise TypeError("MemoryRecord: id must be a non-empty str")
        if not is_memory_kind(self.kind):
            raise ValueError(f"MemoryRecord: kind must be a MemoryKind, got {self.kind!r}")
        if not isinstance(self.content, str):
            raise TypeError(
                f"MemoryRecord: content must be a str, got {type(self.content).__name__}"
            )
        if not isinstance(self.provenance, MemoryProvenance):
            raise TypeError(
                f"MemoryRecord: provenance must be a MemoryProvenance, "
                f"got {type(self.provenance).__name__}"
            )
        if not isinstance(self.created_at, datetime):
            raise TypeError("MemoryRecord: created_at must be a datetime")
        if not isinstance(self.importance, (int, float)) or isinstance(self.importance, bool):
            raise TypeError("MemoryRecord: importance must be a real number")
        if not 0.0 <= float(self.importance) <= 1.0:
            raise ValueError(f"MemoryRecord: importance must be in [0, 1], got {self.importance!r}")
        if self.last_accessed is not None and not isinstance(self.last_accessed, datetime):
            raise TypeError("MemoryRecord: last_accessed must be a datetime or None")

    def recency_anchor(self) -> datetime:
        """Return ``last_accessed`` when set, else ``created_at`` (the recency time)."""
        return self.last_accessed if self.last_accessed is not None else self.created_at

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON-friendly mapping for storage under a ``MemoryStore``."""
        return {
            "id": self.id,
            "kind": self.kind,
            "content": self.content,
            "provenance": self.provenance.to_payload(),
            "created_at": self.created_at.isoformat(),
            "importance": float(self.importance),
            "last_accessed": (
                self.last_accessed.isoformat() if self.last_accessed is not None else None
            ),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_payload(cls, payload: Any) -> MemoryRecord:
        """Reconstruct a record from a mapping previously produced by :meth:`to_payload`.

        Args:
            payload: A mapping carrying at least ``id``/``kind``/``content``/
                ``provenance``/``created_at``.

        Returns:
            The reconstructed :class:`MemoryRecord`.

        Raises:
            TypeError: If ``payload`` is not a mapping.
        """
        if not isinstance(payload, Mapping):
            raise TypeError(
                f"MemoryRecord.from_payload: payload must be a Mapping, "
                f"got {type(payload).__name__}"
            )
        raw_last = payload.get("last_accessed")
        kind = payload["kind"]
        if not is_memory_kind(kind):
            raise ValueError(f"MemoryRecord.from_payload: invalid kind {kind!r}")
        return cls(
            id=str(payload["id"]),
            kind=kind,
            content=str(payload["content"]),
            provenance=MemoryProvenance.from_payload(payload["provenance"]),
            created_at=datetime.fromisoformat(str(payload["created_at"])),
            importance=float(payload.get("importance", 0.0)),
            last_accessed=(datetime.fromisoformat(str(raw_last)) if raw_last is not None else None),
            metadata=dict(payload.get("metadata", {})),
        )

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return self.to_payload()
