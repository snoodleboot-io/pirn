# pyright: reportUnnecessaryIsInstance=false
# runtime-bound knot inputs: explicit type guards are house style (docs/contributing/domain-knots.md)
"""``MemoryRecord`` — one typed, provenance-carrying unit of agent memory.

The single value object every F27 memory-management piece reads and writes.
ADR "agents speaks core" WS3 makes it a
``pirn.core.payload.Payload[MemoryProvenance, MemoryContent]``: the frame
(:class:`~pirn_agents.memory.management.memory_provenance.MemoryProvenance`)
carries ``source``/``trust_signal``/``derivation`` plus the lifecycle
timestamps and ``importance`` that drive decay and ranking; the data
(:class:`~pirn_agents.memory.management.memory_content.MemoryContent`) carries
the stable ``id``, ``kind``, ``content``, and free-form ``tags``. This is the
same frame/data split every other pirn domain payload uses (see
``pirn_signal.types.signal_payload.SignalPayload``), and it is what lets a
writer knot simply *return* a ``MemoryRecord`` as its output: the engine
content-addresses it into ``DataStore`` and records its ``KnotLineage`` row
like any other knot output, with no separate keyed write.

``MemoryRecord``'s own constructor and every domain-readable accessor
(``.id``, ``.kind``, ``.content``, ``.provenance``, ``.created_at``,
``.importance``, ``.last_accessed``) are unchanged from before this split, so
every existing caller — the ``memory_patterns/`` writers, the eviction and
ranking knots, ``MemoryConsolidator`` — keeps working with no changes of its
own. What changed is what backs those accessors: they now read through
``Payload.metadata`` (the frame) and ``Payload.data`` (the content) rather
than being the record's own dataclass fields.

It still round-trips through the untyped
:class:`~pirn_agents.memory.stores.memory_store.MemoryStore` mapping interface
via :meth:`to_payload` / :meth:`from_payload`, so any store built against that
interface keeps reading and writing plain mappings unchanged.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from pirn.core.payload import Payload

from pirn_agents.memory.management.memory_content import MemoryContent
from pirn_agents.memory.management.memory_kind import MemoryKind
from pirn_agents.memory.management.memory_kind_guard import MemoryKindGuard
from pirn_agents.memory.management.memory_provenance import MemoryProvenance


class MemoryRecord(Payload[MemoryProvenance, MemoryContent]):
    """A frozen, typed memory record: a ``MemoryProvenance`` frame + ``MemoryContent`` data."""

    def __init__(
        self,
        *,
        id: str,
        kind: MemoryKind,
        content: str,
        provenance: MemoryProvenance,
        created_at: datetime,
        importance: float = 0.0,
        last_accessed: datetime | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        """Build a record, folding the lifecycle signals onto the ``provenance`` frame.

        Args:
            id: Stable primary key; the store key the record is persisted under.
            kind: The record's :data:`MemoryKind`.
            content: The record's text payload.
            provenance: Origin + trust metadata. The frame this record actually
                carries is ``provenance`` with ``created_at``/``importance``/
                ``last_accessed`` folded in — see the class docstring.
            created_at: Timezone-aware creation time; the recency anchor when
                ``last_accessed`` is unset.
            importance: Caller-assigned importance in ``[0.0, 1.0]``; higher
                survives decay and ranks higher. Defaults to neutral ``0.0``.
            last_accessed: Timezone-aware last-read time, or ``None`` if never
                re-accessed.
            metadata: Arbitrary scalar metadata (e.g. ``session_id``, subject
                keys), carried on :attr:`tags`.

        Raises:
            TypeError: If any argument has the wrong type.
            ValueError: If ``kind`` is not a valid :data:`MemoryKind` or
                ``importance`` is out of ``[0, 1]``.
        """
        if not isinstance(id, str) or not id:
            raise TypeError("MemoryRecord: id must be a non-empty str")
        if not MemoryKindGuard.is_kind(kind):
            raise ValueError(f"MemoryRecord: kind must be a MemoryKind, got {kind!r}")
        if not isinstance(content, str):
            raise TypeError(f"MemoryRecord: content must be a str, got {type(content).__name__}")
        if not isinstance(provenance, MemoryProvenance):
            raise TypeError(
                f"MemoryRecord: provenance must be a MemoryProvenance, "
                f"got {type(provenance).__name__}"
            )
        if not isinstance(created_at, datetime):
            raise TypeError("MemoryRecord: created_at must be a datetime")
        if not isinstance(importance, (int, float)) or isinstance(importance, bool):
            raise TypeError("MemoryRecord: importance must be a real number")
        if not 0.0 <= float(importance) <= 1.0:
            raise ValueError(f"MemoryRecord: importance must be in [0, 1], got {importance!r}")
        if last_accessed is not None and not isinstance(last_accessed, datetime):
            raise TypeError("MemoryRecord: last_accessed must be a datetime or None")
        frame = dataclasses.replace(
            provenance,
            created_at=created_at,
            importance=float(importance),
            last_accessed=last_accessed,
        )
        data = MemoryContent(
            id=id,
            kind=kind,
            content=content,
            tags=dict(metadata) if metadata is not None else {},
        )
        super().__init__(metadata=frame, data=data)

    # -- domain-readable aliases, backed by Payload.metadata / Payload.data --

    @property
    def id(self) -> str:
        return self.data.id

    @property
    def kind(self) -> MemoryKind:
        return self.data.kind

    @property
    def content(self) -> str:
        return self.data.content

    @property
    def tags(self) -> Mapping[str, Any]:
        return self.data.tags

    @property
    def provenance(self) -> MemoryProvenance:
        """The frame carrying source/trust/derivation and this record's lifecycle."""
        return self.metadata

    @property
    def created_at(self) -> datetime:
        created = self.metadata.created_at
        assert created is not None  # always set by __init__
        return created

    @property
    def importance(self) -> float:
        return self.metadata.importance

    @property
    def last_accessed(self) -> datetime | None:
        return self.metadata.last_accessed

    def recency_anchor(self) -> datetime:
        """Return ``last_accessed`` when set, else ``created_at`` (the recency time)."""
        return self.last_accessed if self.last_accessed is not None else self.created_at

    def derive(
        self,
        *,
        id: str,
        content: str,
        kind: MemoryKind | None = None,
        source: str | None = None,
        timestamp: datetime | None = None,
        trust_signal: float | None = None,
        derivation: str | None = None,
        created_at: datetime | None = None,
        importance: float | None = None,
        last_accessed: datetime | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> MemoryRecord:
        """Build a new :class:`MemoryRecord` derived from this one.

        Mirrors ``SignalPayload.derive()``: inherits every frame field this
        record already carries (``source``, ``timestamp``, ``trust_signal``,
        ``created_at``, ``importance``, ``tags``) and overrides only what the
        caller supplies. ``derivation`` and ``id``/``content`` are the two
        fields a caller almost always sets explicitly — a consolidator, for
        example, passes a fresh id, the summarised content, and a
        ``derivation`` note naming its sources.

        Args:
            id: The new record's stable id.
            content: The new record's text payload.
            kind: Overrides this record's kind; defaults to unchanged.
            source: Overrides the frame's ``source``; defaults to unchanged.
            timestamp: Overrides the frame's ``timestamp``; defaults to unchanged.
            trust_signal: Overrides the frame's ``trust_signal``; defaults to
                unchanged.
            derivation: Overrides the frame's ``derivation``; defaults to
                unchanged.
            created_at: Overrides the new record's ``created_at``; defaults to
                this record's ``created_at``.
            importance: Overrides the new record's ``importance``; defaults to
                this record's ``importance``.
            last_accessed: The new record's ``last_accessed``; defaults to
                ``None`` (a derived record has not itself been re-accessed).
            metadata: Overrides the new record's ``tags``; defaults to this
                record's ``tags``.

        Returns:
            The derived :class:`MemoryRecord`.
        """
        base = self.provenance
        new_provenance = MemoryProvenance(
            source=source if source is not None else base.source,
            timestamp=timestamp if timestamp is not None else base.timestamp,
            trust_signal=trust_signal if trust_signal is not None else base.trust_signal,
            derivation=derivation if derivation is not None else base.derivation,
        )
        return MemoryRecord(
            id=id,
            kind=kind if kind is not None else self.kind,
            content=content,
            provenance=new_provenance,
            created_at=created_at if created_at is not None else self.created_at,
            importance=importance if importance is not None else self.importance,
            last_accessed=last_accessed,
            metadata=metadata if metadata is not None else dict(self.tags),
        )

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON-friendly mapping for storage under a ``MemoryStore``."""
        base_provenance = MemoryProvenance(
            source=self.provenance.source,
            timestamp=self.provenance.timestamp,
            trust_signal=self.provenance.trust_signal,
            derivation=self.provenance.derivation,
        )
        return {
            "id": self.id,
            "kind": self.kind,
            "content": self.content,
            "provenance": base_provenance.to_payload(),
            "created_at": self.created_at.isoformat(),
            "importance": float(self.importance),
            "last_accessed": (
                self.last_accessed.isoformat() if self.last_accessed is not None else None
            ),
            "metadata": dict(self.tags),
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
        if not MemoryKindGuard.is_kind(kind):
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

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MemoryRecord):
            return NotImplemented
        return self.metadata == other.metadata and self.data == other.data

    def __hash__(self) -> int:
        return hash((type(self), self.id))

    def __repr__(self) -> str:
        return (
            f"MemoryRecord(id={self.id!r}, kind={self.kind!r}, "
            f"importance={self.importance!r}, provenance={self.provenance!r})"
        )
