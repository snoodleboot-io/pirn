"""Emitter base class."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pirn.emitters.emitter_error_policy import EmitterErrorPolicy  # canonical location

if TYPE_CHECKING:
    from pirn.core.knot_lineage import KnotLineage
    from pirn.core.result import Result
    from pirn.core.run_result import RunResult
    from pirn.managers.status_event import StatusEvent

__all__ = ["Emitter", "EmitterErrorPolicy"]


class Emitter:
    """Base class for run observers.

    Concrete emitters subclass and override the methods they care
    about; the defaults are no-ops.  All emit methods are async — even
    if your emitter does its work synchronously, declaring async lets
    the runtime call it without blocking.

    Two hooks see a finished knot, at two different moments:

    * ``on_knot_result`` fires the instant the knot settles, inside the
      engine's scheduling loop, with the knot's full ``Result`` — the
      ``Ok`` value, the ``Err``'s ``ExceptionRecord``, or the ``Skipped``
      reason — and its lineage row.  It is the live per-knot stream: a
      consumer can act on each item of a fan-out before the join that
      gathers them has even started (ADR agents-speaks-core, WS0b).
    * ``on_lineage`` fires after the run has been persisted, once per row,
      in the run's reported (graph) order.  It sees the same row, but not
      the value, and never before ``history.record_run``.
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

    async def on_knot_result(self, knot_id: str, result: Result[Any], lineage: KnotLineage) -> None:
        """Called the moment a knot settles, with its full outcome.

        Invoked by the engine once per knot per run, inside the scheduling
        loop, as soon as the knot's ``Ok`` / ``Err`` / ``Skipped`` exists
        and its lineage row has been built — before the run finishes, before
        ``history.record_run``, and before any child of the knot is
        dispatched.  Sibling knots therefore stream through here in the
        order they actually finish, not in the run's reported order.

        This is the hook for streaming per-item outcomes out of a fan-out:
        each element knot of a ``Map``-over-``SubTapestry`` or an
        ``Aggregator``'s parents arrives here as it completes, while the
        join is still waiting for the rest.

        The default is a no-op.  It is awaited in place, so keep it quick:
        hand the outcome to a queue or a buffer and return.  A hook that
        raises is treated by the run's ``EmitterErrorPolicy`` exactly like
        ``on_lineage`` — ignored, warned, or raised, in which case the run
        aborts.

        Args:
            knot_id: The settled knot's id.
            result: Its outcome.  For ``Ok`` the value is the in-memory
                value the knot produced (already re-registered against the
                run's ``ExceptionManager`` for ``Err``, so
                ``result.record.run_id`` is this run's id).
            lineage: The ``KnotLineage`` row the engine built for it —
                timing, hashes, outcome, ``extra``.
        """

    async def on_lineage(self, record: KnotLineage) -> None:
        """Called when a lineage record is produced (per knot per run).

        Invoked once per knot after the run has completed and been
        persisted, in the run's reported order.  The record carries timing,
        outcome, output hash, and error information; for the knot's value
        at the moment it settled, see ``on_knot_result``.

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

        Called by :meth:`~pirn.tapestry.Tapestry.close` for every emitter
        registered on that tapestry — either explicitly, or automatically
        on exit from ``async with Tapestry() as t:``.  A plain synchronous
        ``with Tapestry() as t:`` cannot await this and must call
        ``await t.close()`` itself. Implementations should be idempotent and
        must not raise.
        """
