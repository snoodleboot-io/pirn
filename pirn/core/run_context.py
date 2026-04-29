from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from pirn.core.lineage import KnotLineage
from pirn.core.run_result import RunResult
from pirn.managers.exception_manager import ExceptionManager
from pirn.managers.status_manager import StatusManager


class RunContext:
    """Live, run-scoped services carried through the engine."""

    def __init__(
        self,
        run_id: str,
        terminals_requested: list[str],
        dispatcher_name: str,
        parameters: dict[str, Any] | None = None,
        traceback_filter: Callable[[str], str] | None = None,
    ) -> None:
        self.run_id = run_id
        self.terminals_requested = terminals_requested
        self.dispatcher_name = dispatcher_name
        self.parameters: dict[str, Any] = parameters or {}
        self.status = StatusManager(run_id)
        self.exceptions = ExceptionManager(run_id, traceback_filter=traceback_filter)
        self.lineage: list[KnotLineage] = []
        self.skipped: list[str] = []
        self.started_at = datetime.now(UTC)

    def add_lineage(self, record: KnotLineage) -> None:
        self.lineage.append(record)

    def finalize(self, outputs: dict[str, Any]) -> RunResult:
        return RunResult(
            run_id=self.run_id,
            terminals_requested=self.terminals_requested,
            outputs=outputs,
            skipped=self.skipped,
            exceptions=self.exceptions.report(),
            lineage=list(self.lineage),
            status_events=self.status.events(),
            started_at=self.started_at,
            finished_at=datetime.now(UTC),
            dispatcher=self.dispatcher_name,
        )
