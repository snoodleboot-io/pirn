"""``TraceEvent`` — one structured, content-addressed step in a run trajectory."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.determinism.content_digest import content_digest
from pirn_agents.determinism.trace_event_kind import TraceEventKind


@dataclass(frozen=True)
class TraceEvent(PirnOpaqueValue):
    """A single append-only trajectory step: an ordered, timestamped record.

    ``digest`` is a content hash of the payload, so a run diff can tell whether a
    step's input/output changed between two runs without comparing raw payloads.

    Attributes
    ----------
    index:
        0-based position of this event in the trajectory.
    kind:
        Which class of step this event captured.
    name:
        A short label for the step (e.g. the tool name or decision id).
    payload:
        The JSON-serialisable data for the step (arguments, result, decision).
    timestamp:
        ISO-8601 instant the event was captured (from the injected clock).
    """

    index: int
    kind: TraceEventKind
    name: str
    payload: Any
    timestamp: str

    def __post_init__(self) -> None:
        if isinstance(self.index, bool) or not isinstance(self.index, int):
            raise TypeError("TraceEvent: index must be an int")
        if self.index < 0:
            raise ValueError(f"TraceEvent: index must be >= 0, got {self.index}")
        if not isinstance(self.kind, TraceEventKind):
            raise TypeError(
                f"TraceEvent: kind must be a TraceEventKind, got {type(self.kind).__name__}"
            )
        if not isinstance(self.name, str):
            raise TypeError("TraceEvent: name must be a str")

    @property
    def digest(self) -> str:
        """Return the content digest of this event's ``kind``, ``name``, payload."""
        return content_digest([self.kind.value, self.name, self.payload])

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON-friendly mapping of this event."""
        return {
            "index": self.index,
            "kind": self.kind.value,
            "name": self.name,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_payload(cls, payload: Any) -> TraceEvent:
        """Reconstruct an event from a mapping produced by :meth:`to_payload`.

        Raises:
            TypeError: If ``payload`` is not a Mapping.
        """
        if not isinstance(payload, Mapping):
            raise TypeError(
                f"TraceEvent.from_payload: payload must be a Mapping, got {type(payload).__name__}"
            )
        return cls(
            index=int(payload["index"]),
            kind=TraceEventKind(str(payload["kind"])),
            name=str(payload["name"]),
            payload=payload.get("payload"),
            timestamp=str(payload["timestamp"]),
        )

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return self.to_payload()
