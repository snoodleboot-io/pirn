"""``TrajectoryEmitter`` — capture a run's trajectory from the engine itself.

ADR "agents speaks core" WS3 part 3. Where ``TrajectoryRecorder`` (a one-cycle
shim, deleted PIR-864) required every call site to remember to call
``.record(...)``, an ``Emitter``
attached to a ``Tapestry`` sees every knot's lineage automatically —
``on_lineage`` fires once per knot per run, whether or not the pipeline
author thought to instrument that particular step. No manual instrumentation,
no missed steps.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, ClassVar

from pirn.emitters.emitter import Emitter

from pirn_agents.determinism.clock import Clock
from pirn_agents.determinism.run_trace import RunTrace
from pirn_agents.determinism.system_clock import SystemClock
from pirn_agents.determinism.trace_event import TraceEvent
from pirn_agents.determinism.trace_event_kind import TraceEventKind

if TYPE_CHECKING:
    from pirn.core.knot_lineage import KnotLineage


class TrajectoryEmitter(Emitter):
    """Materialises every knot's ``KnotLineage`` into a per-run :class:`RunTrace`.

    Attach to a ``Tapestry`` (``Tapestry(emitters=[emitter])`` or
    ``add_emitter``); after a run, :meth:`trace_for` returns the trace built
    from that run's lineage. One instance may observe many runs — traces are
    kept separately by ``run_id``.
    """

    #: Default classifier: a best-effort guess from the knot's class name.
    #: Callers with real knowledge of their graph should pass their own.
    _default_kind_hints: ClassVar[tuple[tuple[str, TraceEventKind], ...]] = (
        ("llm", TraceEventKind.LLM_CALL),
        ("tool", TraceEventKind.TOOL_CALL),
        ("retriev", TraceEventKind.RETRIEVAL),
    )

    def __init__(
        self,
        *,
        clock: Clock | None = None,
        classify: Callable[[KnotLineage], TraceEventKind] | None = None,
    ) -> None:
        """Initialise the emitter.

        Args:
            clock: The time source for event timestamps; defaults to a live
                :class:`SystemClock`.
            classify: Optional override mapping a lineage row to a
                :class:`TraceEventKind`; defaults to a name-based heuristic
                over ``knot_class`` (falls back to ``OUTPUT``).

        Raises:
            TypeError: If ``clock`` is given but is not a Clock.
        """
        if clock is not None and not isinstance(clock, Clock):
            raise TypeError(f"TrajectoryEmitter: clock must be a Clock, got {type(clock).__name__}")
        self._clock: Clock = clock if clock is not None else SystemClock()
        self._classify = classify if classify is not None else self._default_classify
        self._events_by_run: dict[str, list[TraceEvent]] = {}

    async def on_lineage(self, record: KnotLineage) -> None:
        """Append one :class:`TraceEvent` for ``record`` to its run's trajectory."""
        events = self._events_by_run.setdefault(record.run_id, [])
        events.append(
            TraceEvent(
                index=len(events),
                kind=self._classify(record),
                name=record.knot_id,
                payload={
                    "knot_class": record.knot_class,
                    "outcome": record.outcome,
                    "output_hash": record.output_hash,
                },
                timestamp=self._clock.now().isoformat(),
            )
        )

    def trace_for(self, run_id: str) -> RunTrace:
        """Return the :class:`RunTrace` captured for ``run_id`` so far."""
        return RunTrace(run_id=run_id, events=tuple(self._events_by_run.get(run_id, ())))

    def forget(self, run_id: str) -> None:
        """Drop the retained events for ``run_id`` (bound memory for long-lived emitters)."""
        self._events_by_run.pop(run_id, None)

    @staticmethod
    def _default_classify(record: KnotLineage) -> TraceEventKind:
        """A best-effort guess from ``record.knot_class``'s name."""
        name = record.knot_class.lower()
        for hint, kind in TrajectoryEmitter._default_kind_hints:
            if hint in name:
                return kind
        return TraceEventKind.OUTPUT
