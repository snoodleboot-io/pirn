from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from pirn.core.lineage import KnotLineage
from pirn.managers.exception_record import ExceptionRecord
from pirn.managers.status_event import StatusEvent


class RunResult(BaseModel):
    """The fully self-contained, serialisable outcome of a single tapestry run.

    ``RunResult`` is produced by ``Tapestry.run()`` after the scheduler has
    finished executing (or failing) every knot in the requested subgraph.  It
    is intentionally frozen so it can be safely cached, shipped over a
    message bus, or written to a data store without defensive copying.

    Attributes:
        run_id: Unique identifier for this run, matching the id in the
            originating ``RunRequest``.
        terminals_requested: Knot ids the caller nominated as run terminals,
            or the tapestry's leaf knots when the caller passed none.
        outputs: Mapping of ``knot_id`` → output value for every knot that
            completed with an ``Ok`` result.  Knots that were skipped or
            raised an error are absent.
        skipped: Knot ids that were deliberately not executed (e.g. closed
            gate, non-selected branch arm, or upstream skip propagation).
        exceptions: ``ExceptionRecord`` entries for every knot that raised,
            in execution order.
        lineage: ``KnotLineage`` rows — one per knot invocation — forming the
            lineage graph for this run.
        status_events: Ordered stream of ``StatusEvent`` objects emitted by
            knots and the scheduler during the run.
        started_at: Wall-clock UTC timestamp recorded just before the
            scheduler dispatched the first knot.
        finished_at: Wall-clock UTC timestamp recorded immediately after the
            scheduler finished (success or failure).
        dispatcher: Name of the dispatcher class used for this run (e.g.
            ``'LocalDispatcher'``).
        run_path: Materialised path identifying this run's position in a
            nested sub-tapestry hierarchy.  Format: ``/{run_id}`` for root
            runs, ``/{parent_run_id}/{run_id}`` for nested runs.
        parent_run_id: ``run_id`` of the outer run that spawned this one via a
            ``SubTapestry`` knot.  ``None`` for root runs.
        parent_knot_id: ``knot_id`` of the ``SubTapestry`` knot in the parent
            run that triggered this run.  ``None`` for root runs.
        actor: Who initiated the run — user id, service account, or API key
            label.  ``None`` when not provided by the trigger.
        environment: Where the run executed — hostname, region, deployment
            environment, and similar key/value pairs.
        trigger: Why the run was initiated — trigger type and identifier, e.g.
            ``'webhook:order-placed'`` or ``'manual'``.
        runtime_info: By what means — Python version, pirn version, platform,
            and other runtime metadata.
    """

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
