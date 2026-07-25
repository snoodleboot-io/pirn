"""``MemoryProvenance`` — where a memory came from and how much to trust it.

Every :class:`~pirn_agents.memory_management.memory_record.MemoryRecord` carries a
provenance value object recording its ``source`` (the producing subsystem or
tool), the ``timestamp`` it was captured, a ``trust_signal`` in ``[0, 1]``, and
an optional ``derivation`` note describing how a derived record was produced
(e.g. ``"consolidated-from:<ids>"``). Provenance is a frozen, opaque value object
so it travels through the pirn graph without entering the content hash by value;
it is the soft tie-in point for F11 trust (F11 consumes ``trust_signal`` without
this package depending on F11).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class MemoryProvenance(PirnOpaqueValue):
    """Immutable origin + trust metadata for one memory record.

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
    """

    source: str
    timestamp: datetime
    trust_signal: float = 1.0
    derivation: str | None = None

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

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON-friendly mapping for storage under a ``MemoryStore``."""
        return {
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "trust_signal": float(self.trust_signal),
            "derivation": self.derivation,
        }

    @classmethod
    def from_payload(cls, payload: Any) -> MemoryProvenance:
        """Reconstruct provenance from a mapping previously produced by :meth:`to_payload`.

        Args:
            payload: A mapping with ``source``/``timestamp`` and optional
                ``trust_signal``/``derivation``.

        Returns:
            The reconstructed :class:`MemoryProvenance`.

        Raises:
            TypeError: If ``payload`` is not a mapping.
        """
        if not isinstance(payload, Mapping):
            raise TypeError(
                f"MemoryProvenance.from_payload: payload must be a Mapping, "
                f"got {type(payload).__name__}"
            )
        raw_trust = payload.get("trust_signal", 1.0)
        return cls(
            source=str(payload["source"]),
            timestamp=datetime.fromisoformat(str(payload["timestamp"])),
            trust_signal=float(raw_trust),
            derivation=payload.get("derivation"),
        )

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return self.to_payload()
