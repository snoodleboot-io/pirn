"""``ProvenanceTag`` — where a piece of untrusted content came from.

A :class:`ProvenanceTag` is the immutable origin + trust label attached to every
tool / RAG / MCP payload before it is wrapped as untrusted content. It records
the ``source_kind`` (``"tool"``, ``"rag"``, ``"mcp"``, …), the ``source_name``
(the concrete tool / retriever / server), the capture ``timestamp``, and a
``trust_signal`` in ``[0, 1]``.

It is the F11 counterpart of F27's
:class:`~pirn_agents.memory_management.memory_provenance.MemoryProvenance`; the
:meth:`from_memory_provenance` bridge lets a memory record's provenance flow
straight into an untrusted-content wrap without either package depending on the
other by value.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class ProvenanceTag(PirnOpaqueValue):
    """Immutable origin + trust label for one untrusted payload.

    Attributes
    ----------
    source_kind:
        Non-empty class of producer: ``"tool"``, ``"rag"``, ``"mcp"``, or any
        other subsystem label.
    source_name:
        Non-empty concrete producer name (a tool name, retriever id, or MCP
        server / tool identifier).
    timestamp:
        Timezone-aware capture time.
    trust_signal:
        Confidence in ``[0.0, 1.0]``; defaults to a low ``0.0`` because
        externally-sourced content is untrusted until screened.
    """

    source_kind: str
    source_name: str
    timestamp: datetime
    trust_signal: float = 0.0

    def __post_init__(self) -> None:
        """Validate the field types and the ``trust_signal`` domain.

        Raises
        ------
        TypeError
            If ``source_kind`` / ``source_name`` are not non-empty strings, the
            ``timestamp`` is not a :class:`datetime`, or ``trust_signal`` is not
            a real number.
        ValueError
            If ``trust_signal`` falls outside ``[0, 1]``.
        """
        if not isinstance(self.source_kind, str) or not self.source_kind:
            raise TypeError("ProvenanceTag: source_kind must be a non-empty str")
        if not isinstance(self.source_name, str) or not self.source_name:
            raise TypeError("ProvenanceTag: source_name must be a non-empty str")
        if not isinstance(self.timestamp, datetime):
            raise TypeError(
                f"ProvenanceTag: timestamp must be a datetime, got {type(self.timestamp).__name__}"
            )
        if isinstance(self.trust_signal, bool) or not isinstance(self.trust_signal, (int, float)):
            raise TypeError("ProvenanceTag: trust_signal must be a real number")
        if not 0.0 <= float(self.trust_signal) <= 1.0:
            raise ValueError(
                f"ProvenanceTag: trust_signal must be in [0, 1], got {self.trust_signal!r}"
            )

    @property
    def label(self) -> str:
        """Return the compact ``"<source_kind>:<source_name>"`` label."""
        return f"{self.source_kind}:{self.source_name}"

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON-friendly mapping of the tag."""
        return {
            "source_kind": self.source_kind,
            "source_name": self.source_name,
            "timestamp": self.timestamp.isoformat(),
            "trust_signal": float(self.trust_signal),
        }

    @classmethod
    def from_memory_provenance(
        cls, provenance: Any, *, source_kind: str = "memory"
    ) -> ProvenanceTag:
        """Bridge an F27 ``MemoryProvenance`` into a :class:`ProvenanceTag`.

        Args:
            provenance: A
                :class:`~pirn_agents.memory_management.memory_provenance.MemoryProvenance`
                (duck-typed on ``source``/``timestamp``/``trust_signal``).
            source_kind: The ``source_kind`` to record; defaults to ``"memory"``.

        Returns:
            The equivalent :class:`ProvenanceTag`.
        """
        return cls(
            source_kind=source_kind,
            source_name=str(provenance.source),
            timestamp=provenance.timestamp,
            trust_signal=float(provenance.trust_signal),
        )

    @classmethod
    def from_payload(cls, payload: Any) -> ProvenanceTag:
        """Reconstruct a tag from a mapping produced by :meth:`to_payload`.

        Raises:
            TypeError: If ``payload`` is not a mapping.
        """
        if not isinstance(payload, Mapping):
            raise TypeError(
                f"ProvenanceTag.from_payload: payload must be a Mapping, "
                f"got {type(payload).__name__}"
            )
        return cls(
            source_kind=str(payload["source_kind"]),
            source_name=str(payload["source_name"]),
            timestamp=datetime.fromisoformat(str(payload["timestamp"])),
            trust_signal=float(payload.get("trust_signal", 0.0)),
        )

    def _pirn_audit_dict(self) -> dict[str, Any]:
        """Return a stable content-addressing view of the tag."""
        return self.to_payload()
