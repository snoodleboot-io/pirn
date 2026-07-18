"""``TrajectoryRecorder`` — a cheap, append-only capture of a run's steps."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn_agents.determinism.clock import Clock
from pirn_agents.determinism.run_trace import RunTrace
from pirn_agents.determinism.system_clock import SystemClock
from pirn_agents.determinism.trace_event import TraceEvent
from pirn_agents.determinism.trace_event_kind import TraceEventKind


class TrajectoryRecorder:
    """Collect a run's steps into a versioned :class:`RunTrace`, low-overhead.

    Each :meth:`record` is a single list append plus one injected-clock read, so
    capture overhead is negligible relative to the run itself. Timestamps come
    from the injected :class:`Clock` (a frozen clock in deterministic mode), and
    :meth:`snapshot` materialises the immutable trace at any point.
    """

    def __init__(
        self,
        *,
        run_id: str,
        clock: Clock | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        """Initialise a recorder for ``run_id``.

        Args:
            run_id: Stable id of the run being traced.
            clock: The time source for event timestamps; defaults to a live
                :class:`SystemClock`.
            metadata: Optional run-level context stored on the trace.

        Raises:
            TypeError: If ``run_id`` is empty or ``clock`` is not a Clock.
        """
        if not isinstance(run_id, str) or not run_id:
            raise TypeError("TrajectoryRecorder: run_id must be a non-empty str")
        if clock is not None and not isinstance(clock, Clock):
            raise TypeError(
                f"TrajectoryRecorder: clock must be a Clock, got {type(clock).__name__}"
            )
        self._run_id = run_id
        self._clock: Clock = clock if clock is not None else SystemClock()
        self._metadata: dict[str, Any] = dict(metadata) if metadata is not None else {}
        self._events: list[TraceEvent] = []

    @property
    def event_count(self) -> int:
        """Return the number of steps captured so far."""
        return len(self._events)

    def record(self, *, kind: TraceEventKind, name: str, payload: Any) -> TraceEvent:
        """Append and return one trajectory step.

        Args:
            kind: The class of step being captured.
            name: A short label for the step.
            payload: JSON-serialisable data for the step.

        Returns:
            The appended :class:`TraceEvent`.

        Raises:
            TypeError: If ``kind`` is not a TraceEventKind.
        """
        if not isinstance(kind, TraceEventKind):
            raise TypeError(
                f"TrajectoryRecorder.record: kind must be a TraceEventKind, "
                f"got {type(kind).__name__}"
            )
        event = TraceEvent(
            index=len(self._events),
            kind=kind,
            name=name,
            payload=payload,
            timestamp=self._clock.now().isoformat(),
        )
        self._events.append(event)
        return event

    def snapshot(self) -> RunTrace:
        """Materialise the immutable :class:`RunTrace` captured so far."""
        return RunTrace(
            run_id=self._run_id,
            events=tuple(self._events),
            metadata=dict(self._metadata),
        )
