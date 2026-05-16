"""Emitter base class."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pirn.emitters.emitter_error_policy import EmitterErrorPolicy  # canonical location

if TYPE_CHECKING:
    from pirn.core.lineage import KnotLineage
    from pirn.core.run_result import RunResult
    from pirn.managers.status_event import StatusEvent

__all__ = ["Emitter", "EmitterErrorPolicy"]


class Emitter:
    """Base class for run observers.

    Concrete emitters subclass and override the methods they care
    about; the defaults are no-ops.  All emit methods are async — even
    if your emitter does its work synchronously, declaring async lets
    the runtime call it without blocking.
    """

    @property
    def name(self) -> str:
        """Human-readable identifier for this emitter, used in logs and error messages."""
        return type(self).__name__

    async def on_status(self, event: StatusEvent) -> None:
        """Called for every per-knot state transition.

        Invoked by the engine each time a knot moves between states
        (e.g. PENDING → RUNNING → SUCCEEDED).  Multiple calls per knot
        per run are expected.

        Args:
            event: The status event describing the knot, run, new state,
                and any detail message.
        """

    async def on_lineage(self, record: KnotLineage) -> None:
        """Called when a lineage record is produced (per knot per run).

        Invoked once per knot after the knot finishes (succeeded, failed,
        or skipped).  The record carries timing, outcome, output hash, and
        error information.

        Args:
            record: The lineage record for the completed knot execution.
        """

    async def on_run_result(self, result: RunResult) -> None:
        """Called when a run completes (success or failure).

        Invoked once per ``tapestry.run()`` call after all knots have
        settled.  The result summarises the entire run.

        Args:
            result: The run result containing overall success/failure,
                timing, and the list of terminal knots requested.
        """

    async def close(self) -> None:
        """Release any held resources (connections, buffers, file handles).

        Called by the runtime when it is done with this emitter.
        Implementations should be idempotent and must not raise.
        """
