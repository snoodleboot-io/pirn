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

``MemoryRecord``'s constructor takes the record's fields by name; they are read
back through the ``Payload`` contract only — ``data.id``/``data.kind``/
``data.content``/``data.tags`` and ``metadata.created_at``/``metadata.importance``/
``metadata.last_accessed`` (``metadata`` is the provenance frame itself).
:meth:`recency_anchor` is the one derived value it adds.

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

from pirn_agents._internal.json_shape import JsonShape
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

    def recency_anchor(self) -> datetime:
        """Return ``last_accessed`` when set, else ``created_at`` (the recency time)."""
        if self.metadata.last_accessed is not None:
            return self.metadata.last_accessed
        return self._created_at()

    def _created_at(self) -> datetime:
        """Return the frame's ``created_at``, which ``__init__`` always sets on a record.

        Raises:
            ValueError: If the frame carries no ``created_at`` (never for a record
                built through ``__init__``).
        """
        created = self.metadata.created_at
        if created is None:
            raise ValueError("MemoryRecord: frame carries no created_at")
        return created

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
        base = self.metadata
        new_provenance = MemoryProvenance(
            source=source if source is not None else base.source,
            timestamp=timestamp if timestamp is not None else base.timestamp,
            trust_signal=trust_signal if trust_signal is not None else base.trust_signal,
            derivation=derivation if derivation is not None else base.derivation,
        )
        return MemoryRecord(
            id=id,
            kind=kind if kind is not None else self.data.kind,
            content=content,
            provenance=new_provenance,
            created_at=created_at if created_at is not None else self._created_at(),
            importance=importance if importance is not None else self.metadata.importance,
            last_accessed=last_accessed,
            metadata=metadata if metadata is not None else dict(self.data.tags),
        )

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON-friendly mapping for storage under a ``MemoryStore``."""
        base_provenance = MemoryProvenance(
            source=self.metadata.source,
            timestamp=self.metadata.timestamp,
            trust_signal=self.metadata.trust_signal,
            derivation=self.metadata.derivation,
        )
        return {
            "id": self.data.id,
            "kind": self.data.kind,
            "content": self.data.content,
            "provenance": base_provenance.to_payload(),
            "created_at": self._created_at().isoformat(),
            "importance": float(self.metadata.importance),
            "last_accessed": (
                self.metadata.last_accessed.isoformat()
                if self.metadata.last_accessed is not None
                else None
            ),
            "metadata": dict(self.data.tags),
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
        if not JsonShape.is_mapping(payload):
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
        return hash((type(self), self.data.id))

    def __repr__(self) -> str:
        return (
            f"MemoryRecord(id={self.data.id!r}, kind={self.data.kind!r}, "
            f"importance={self.metadata.importance!r}, provenance={self.metadata!r})"
        )
