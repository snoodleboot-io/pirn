"""``RunTrace`` — a versioned, append-only structured trajectory of a run."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.determinism.trace_event import TraceEvent


@dataclass(frozen=True)
class RunTrace(PirnOpaqueValue):
    """The full, serialisable trace of a run: inputs, decisions, calls, outputs.

    Append-only and immutable — :meth:`with_event` returns a new trace — so a
    trajectory is a faithful, low-overhead record. The ``schema_version`` field
    versions the on-disk format so a stored trace is forward-readable, and
    ``metadata`` carries run-level context (seed, ``forked_from`` provenance).

    Attributes
    ----------
    run_id:
        Stable id of the run this trace belongs to.
    events:
        The captured steps, in record order.
    metadata:
        Run-level context (e.g. seed, deterministic flag, fork provenance).
    schema_version:
        The trace schema version tag.
    """

    run_id: str
    events: tuple[TraceEvent, ...] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = "f29-trace/1"

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, str) or not self.run_id:
            raise TypeError("RunTrace: run_id must be a non-empty str")
        if not isinstance(self.events, tuple):
            raise TypeError(f"RunTrace: events must be a tuple, got {type(self.events).__name__}")
        for event in self.events:
            if not isinstance(event, TraceEvent):
                raise TypeError(
                    f"RunTrace: every event must be a TraceEvent, got {type(event).__name__}"
                )

    def with_event(self, event: TraceEvent) -> RunTrace:
        """Return a new trace with ``event`` appended.

        Raises:
            TypeError: If ``event`` is not a TraceEvent.
        """
        if not isinstance(event, TraceEvent):
            raise TypeError(
                f"RunTrace.with_event: event must be a TraceEvent, got {type(event).__name__}"
            )
        return RunTrace(
            run_id=self.run_id,
            events=(*self.events, event),
            metadata=dict(self.metadata),
            schema_version=self.schema_version,
        )

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON-friendly mapping capturing the whole trace."""
        return {
            "run_id": self.run_id,
            "schema_version": self.schema_version,
            "metadata": dict(self.metadata),
            "events": [event.to_payload() for event in self.events],
        }

    @classmethod
    def from_payload(cls, payload: Any) -> RunTrace:
        """Reconstruct a trace from a mapping produced by :meth:`to_payload`.

        Raises:
            TypeError: If ``payload`` is not a Mapping.
        """
        if not isinstance(payload, Mapping):
            raise TypeError(
                f"RunTrace.from_payload: payload must be a Mapping, got {type(payload).__name__}"
            )
        raw: Sequence[Any] = payload.get("events", ())
        metadata: Mapping[str, Any] = payload.get("metadata", {})
        return cls(
            run_id=str(payload["run_id"]),
            events=tuple(TraceEvent.from_payload(item) for item in raw),
            metadata=dict(metadata),
            schema_version=str(payload.get("schema_version", "f29-trace/1")),
        )

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return self.to_payload()
