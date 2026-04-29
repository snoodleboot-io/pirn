"""Emitter protocol and a no-op base class."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pirn.core.context import RunResult
    from pirn.core.lineage import KnotLineage
    from pirn.managers.status import StatusEvent


class Emitter:
    """Base class for run observers.

    Concrete emitters subclass and override the methods they care
    about; the defaults are no-ops.  All emit methods are async — even
    if your emitter does its work synchronously, declaring async lets
    the runtime call it without blocking.
    """

    @property
    def name(self) -> str:
        return type(self).__name__

    async def on_status(self, event: StatusEvent) -> None:
        """Called for every per-knot state transition."""

    async def on_lineage(self, record: KnotLineage) -> None:
        """Called when a lineage record is produced (per knot per run)."""

    async def on_run_result(self, result: RunResult) -> None:
        """Called when a run completes (success or failure)."""

    async def close(self) -> None:
        """Release any resources."""
