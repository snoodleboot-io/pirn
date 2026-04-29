"""Run-scoped context, request, and result objects.

``RunContext`` carries live services through a run.  ``RunRequest`` and
``RunResult`` are Pydantic data models.

Phase 2 changes from Phase 1
----------------------------
* ``RunResult`` now carries the lineage records, terminals_requested, and
  per-knot timings (via the lineage records).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from pirn.core.lineage import KnotLineage
from pirn.managers.exceptions import ExceptionManager, ExceptionRecord
from pirn.managers.status import StatusEvent, StatusManager


class RunRequest(BaseModel):
    """Input to a tapestry run.

    Carries parameter bindings and a run id.  Triggers (Phase 3) build
    these from external events; in Phase 2 the caller builds them
    directly.
    """

    model_config = ConfigDict(frozen=True)

    run_id: str = Field(default_factory=lambda: f"run-{uuid.uuid4().hex[:12]}")
    parameters: dict[str, Any] = Field(default_factory=dict)
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RunResult(BaseModel):
    """The outcome of a run — fully self-contained, serialisable."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    run_id: str
    terminals_requested: list[str] = Field(
        ...,
        description="Knot ids the caller passed as terminals (or those derived "
        "from the tapestry's leaves).",
    )
    outputs: dict[str, Any] = Field(
        ...,
        description="Per-knot output values for knots that produced Ok results.",
    )
    skipped: list[str] = Field(
        default_factory=list,
        description="Knot ids that were skipped (Optional opt-out, "
        "branch not selected, gate closed, parent failure, etc.).",
    )
    exceptions: list[ExceptionRecord] = Field(default_factory=list)
    lineage: list[KnotLineage] = Field(
        default_factory=list,
        description="One record per knot per execution.  See ``KnotLineage``.",
    )
    status_events: list[StatusEvent] = Field(default_factory=list)
    started_at: datetime
    finished_at: datetime
    dispatcher: str = Field(
        ...,
        description="Name of the dispatcher used for this run.",
    )

    @property
    def succeeded(self) -> bool:
        return not self.exceptions

    @property
    def duration_seconds(self) -> float:
        return (self.finished_at - self.started_at).total_seconds()


class RunContext:
    """Live, run-scoped services carried through the engine."""

    def __init__(
        self,
        run_id: str,
        terminals_requested: list[str],
        dispatcher_name: str,
        parameters: dict[str, Any] | None = None,
    ) -> None:
        self.run_id = run_id
        self.terminals_requested = terminals_requested
        self.dispatcher_name = dispatcher_name
        self.parameters: dict[str, Any] = parameters or {}
        self.status = StatusManager(run_id)
        self.exceptions = ExceptionManager(run_id)
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
