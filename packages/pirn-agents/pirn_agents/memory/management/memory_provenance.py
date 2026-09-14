# pyright: reportUnnecessaryIsInstance=false
# runtime-bound knot inputs: explicit type guards are house style (docs/contributing/domain-knots.md)
"""``MemoryProvenance`` — where a memory came from and how much to trust it.

Every :class:`~pirn_agents.memory.management.memory_record.MemoryRecord` carries a
provenance value object recording its ``source`` (the producing subsystem or
tool), the ``timestamp`` it was captured, a ``trust_signal`` in ``[0, 1]``, and
an optional ``derivation`` note describing how a derived record was produced
(e.g. ``"consolidated-from:<ids>"``). Provenance is a frozen, opaque value object
so it travels through the pirn graph without entering the content hash by value;
it is the soft tie-in point for F11 trust (F11 consumes ``trust_signal`` without
this package depending on F11).

ADR "agents speaks core" WS3 makes ``MemoryProvenance`` the frame half of
:class:`~pirn_agents.memory.management.memory_record.MemoryRecord`, which is a
``pirn.core.payload.Payload[MemoryProvenance, MemoryContent]``. A payload frame
carries provenance, lineage, and structural context (see ``pirn.core.payload``),
so the record's lifecycle signals — ``created_at``, ``importance``, and
``last_accessed`` — move here from ``MemoryRecord`` itself: source, trust, and
timestamps live together on the frame. ``MemoryRecord`` still accepts them as
constructor arguments (its public shape is unchanged) and folds them onto the
frame it builds; a ``MemoryProvenance`` used on its own (e.g.
:class:`~pirn_agents.memory.management.entity_profile.EntityProfile`, which has
no separate lifecycle fields) simply leaves the three at their neutral
defaults.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents._internal.json_shape import JsonShape


@dataclass(frozen=True)
class MemoryProvenance(PirnOpaqueValue):
    """Immutable origin + trust + lifecycle metadata for one memory record.

    Attributes
    ----------
    source:
        Non-empty label for the producer (e.g. ``"episodic_writer"``,
        ``"consolidator"``, a tool name).
    timestamp:
        Timezone-aware capture time; used by recency scoring and conflict
        resolution.
    trust_signal:
        Confidence in ``[0.0, 1.0]``; consumed by F11 trust and by
        conflict-resolution tie-breaking. Defaults to fully trusted.
    derivation:
        Optional note on how a derived record was produced, or ``None`` for a
        primary capture.
    created_at:
        Timezone-aware creation time of the record this frame belongs to, or
        ``None`` when this provenance is not attached to a lifecycle-tracked
        record (e.g. a bare provenance stamp on an :class:`EntityProfile`).
    importance:
        Caller-assigned importance in ``[0.0, 1.0]``; higher survives decay and
        ranks higher. Defaults to neutral ``0.0``.
    last_accessed:
        Timezone-aware last-read time, or ``None`` if never re-accessed.
    """

    source: str
    timestamp: datetime
    trust_signal: float = 1.0
    derivation: str | None = None
    created_at: datetime | None = None
    importance: float = 0.0
    last_accessed: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.source, str) or not self.source:
            raise TypeError("MemoryProvenance: source must be a non-empty str")
        if not isinstance(self.timestamp, datetime):
            raise TypeError(
                f"MemoryProvenance: timestamp must be a datetime, "
                f"got {type(self.timestamp).__name__}"
            )
        if not isinstance(self.trust_signal, (int, float)) or isinstance(self.trust_signal, bool):
            raise TypeError("MemoryProvenance: trust_signal must be a real number")
        if not 0.0 <= float(self.trust_signal) <= 1.0:
            raise ValueError(
                f"MemoryProvenance: trust_signal must be in [0, 1], got {self.trust_signal!r}"
            )
        if self.derivation is not None and not isinstance(self.derivation, str):
            raise TypeError("MemoryProvenance: derivation must be a str or None")
        if self.created_at is not None and not isinstance(self.created_at, datetime):
            raise TypeError("MemoryProvenance: created_at must be a datetime or None")
        if not isinstance(self.importance, (int, float)) or isinstance(self.importance, bool):
            raise TypeError("MemoryProvenance: importance must be a real number")
        if not 0.0 <= float(self.importance) <= 1.0:
            raise ValueError(
                f"MemoryProvenance: importance must be in [0, 1], got {self.importance!r}"
            )
        if self.last_accessed is not None and not isinstance(self.last_accessed, datetime):
            raise TypeError("MemoryProvenance: last_accessed must be a datetime or None")

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON-friendly mapping for storage under a ``MemoryStore``."""
        return {
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "trust_signal": float(self.trust_signal),
            "derivation": self.derivation,
            "created_at": self.created_at.isoformat() if self.created_at is not None else None,
            "importance": float(self.importance),
            "last_accessed": (
                self.last_accessed.isoformat() if self.last_accessed is not None else None
            ),
        }

    @classmethod
    def from_payload(cls, payload: Any) -> MemoryProvenance:
        """Reconstruct provenance from a mapping previously produced by :meth:`to_payload`.

        Args:
            payload: A mapping with ``source``/``timestamp`` and optional
                ``trust_signal``/``derivation``/``created_at``/``importance``/
                ``last_accessed``.

        Returns:
            The reconstructed :class:`MemoryProvenance`.

        Raises:
            TypeError: If ``payload`` is not a mapping.
        """
        if not JsonShape.is_mapping(payload):
            raise TypeError(
                f"MemoryProvenance.from_payload: payload must be a Mapping, "
                f"got {type(payload).__name__}"
            )
        raw_trust = payload.get("trust_signal", 1.0)
        raw_created_at = payload.get("created_at")
        raw_last_accessed = payload.get("last_accessed")
        return cls(
            source=str(payload["source"]),
            timestamp=datetime.fromisoformat(str(payload["timestamp"])),
            trust_signal=float(raw_trust),
            derivation=payload.get("derivation"),
            created_at=(datetime.fromisoformat(str(raw_created_at)) if raw_created_at else None),
            importance=float(payload.get("importance", 0.0)),
            last_accessed=(
                datetime.fromisoformat(str(raw_last_accessed)) if raw_last_accessed else None
            ),
        )

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return self.to_payload()
