from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from pirn.core.lineage import KnotLineage
from pirn.managers.exception_record import ExceptionRecord
from pirn.managers.status_event import StatusEvent


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
    skipped: list[str] = Field(default_factory=list)
    exceptions: list[ExceptionRecord] = Field(default_factory=list)
    lineage: list[KnotLineage] = Field(default_factory=list)
    status_events: list[StatusEvent] = Field(default_factory=list)
    started_at: datetime
    finished_at: datetime
    dispatcher: str = Field(..., description="Name of the dispatcher used for this run.")

    # Nesting — set when this run was spawned by a SubTapestry knot
    run_path: str = Field(
        default="",
        description="Materialized path identifying this run's position in the nesting hierarchy. "
        "Format: /{run_id} for root runs. Set by Tapestry.run().",
    )
    parent_run_id: str | None = Field(
        None,
        description="run_id of the outer run that spawned this run via a SubTapestry knot.",
    )
    parent_knot_id: str | None = Field(
        None,
        description="knot_id of the SubTapestry knot in the parent run that triggered this run.",
    )

    # 7 W's — run-level provenance
    actor: str | None = Field(
        None,
        description="Who initiated the run (user id, service account, API key label).",
    )
    environment: dict[str, str] = Field(
        default_factory=dict,
        description="Where the run executed — hostname, region, deployment env, etc.",
    )
    trigger: str | None = Field(
        None,
        description="Why the run was initiated — trigger type and identifier, e.g. "
        "'webhook:order-placed' or 'manual'.",
    )
    runtime_info: dict[str, str] = Field(
        default_factory=dict,
        description="By what means — Python version, pirn version, platform.",
    )

    @property
    def succeeded(self) -> bool:
        return not self.exceptions

    @property
    def duration_seconds(self) -> float:
        return (self.finished_at - self.started_at).total_seconds()
