"""``TraceInspector`` — step through a recorded :class:`RunTrace` for debugging."""

from __future__ import annotations

from pirn_agents.determinism.run_trace import RunTrace
from pirn_agents.determinism.trace_event import TraceEvent
from pirn_agents.determinism.trace_event_kind import TraceEventKind


class TraceInspector:
    """A read-only cursor over a captured trajectory for time-travel debugging.

    Wraps a :class:`RunTrace` and exposes random access (:meth:`event_at`), a
    forward cursor (:meth:`step` / :meth:`has_next` / :meth:`reset`), and kind
    filtering (:meth:`events_of_kind`), so a recorded run can be inspected
    step-by-step without re-executing it.
    """

    def __init__(self, trace: RunTrace) -> None:
        """Initialise the inspector over ``trace``.

        Raises:
            TypeError: If ``trace`` is not a RunTrace.
        """
        if not isinstance(trace, RunTrace):
            raise TypeError(f"TraceInspector: trace must be a RunTrace, got {type(trace).__name__}")
        self._trace = trace
        self._cursor = 0

    @property
    def step_count(self) -> int:
        """Return the total number of steps in the trace."""
        return len(self._trace.events)

    @property
    def position(self) -> int:
        """Return the current cursor position (index of the next step)."""
        return self._cursor

    @property
    def has_next(self) -> bool:
        """Return ``True`` when there is another step to :meth:`step` into."""
        return self._cursor < len(self._trace.events)

    def event_at(self, index: int) -> TraceEvent:
        """Return the step at ``index`` (random access, cursor unchanged).

        Raises:
            IndexError: If ``index`` is out of range.
        """
        if index < 0 or index >= len(self._trace.events):
            raise IndexError(
                f"TraceInspector.event_at: index {index} out of range "
                f"[0, {len(self._trace.events)})"
            )
        return self._trace.events[index]

    def step(self) -> TraceEvent | None:
        """Return the next step and advance the cursor, or ``None`` at the end."""
        if not self.has_next:
            return None
        event = self._trace.events[self._cursor]
        self._cursor += 1
        return event

    def reset(self) -> None:
        """Rewind the cursor to the start of the trace."""
        self._cursor = 0

    def events_of_kind(self, kind: TraceEventKind) -> tuple[TraceEvent, ...]:
        """Return all steps of ``kind`` in order (cursor unchanged).

        Raises:
            TypeError: If ``kind`` is not a TraceEventKind.
        """
        if not isinstance(kind, TraceEventKind):
            raise TypeError(
                f"TraceInspector.events_of_kind: kind must be a TraceEventKind, "
                f"got {type(kind).__name__}"
            )
        return tuple(event for event in self._trace.events if event.kind is kind)
