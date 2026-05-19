"""Lineage records — what ran, on what inputs, producing what outputs.

A ``KnotLineage`` record is produced for every knot invocation in every
run.  Together they form the lineage graph for that run.  Across runs,
records share input/output hashes — that's how cross-run lineage queries
work without any extra infrastructure.

The record references values by content hash, not by content itself.  The
actual values live in a ``DataStore`` keyed by the same hash.  This split
is what makes scrubbing safe: data can be purged after its TTL while
lineage is retained indefinitely (the hash still matches across other
runs that consumed the same value).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class KnotLineage(BaseModel):
    """Immutable record of a single knot invocation within a single run.

    One ``KnotLineage`` row is written for every knot the scheduler attempts,
    regardless of outcome.  Together the rows form the lineage graph for a
    run.  Across runs, rows are joined by their ``output_hash`` /
    ``parent_input_hashes`` content hashes, enabling cross-run provenance
    queries without a separate index.

    Values are never stored directly in lineage rows — only their content
    hashes appear here.  The actual values live in a ``DataStore`` keyed by
    the same hash.  This separation allows data to be purged after its TTL
    while the lineage ledger is retained indefinitely; hash references remain
    valid even after the underlying data is gone.

    Attributes:
        run_id: Identifies the run this invocation belongs to.
        knot_id: The ``KnotConfig.id`` of the knot that was invoked.
        knot_class: Fully-qualified class name of the knot (e.g.
            ``'my_pkg.knots.EnrichUser'``).  Used for cross-run filtering by
            knot type.
        knot_config_hash: Content hash of the knot's serialised
            ``KnotConfig``.  A change in this hash between runs means the
            knot's configuration changed.
        parent_input_hashes: Mapping of ``process()`` parameter name →
            content hash of the value supplied by that parent.  Empty for
            source knots (e.g. ``Parameter``).
        output_hash: Content hash of the knot's output value.  ``None`` when
            the knot failed or was skipped.
        outcome: One of ``'ok'``, ``'err'``, or ``'skipped'``.
        error_record_id: When ``outcome == 'err'``, the run-scoped id of the
            ``ExceptionRecord`` registered with the run's
            ``ExceptionManager``.  ``None`` otherwise.
        skip_reason: Human-readable explanation of why the knot was skipped.
            ``None`` when ``outcome != 'skipped'``.
        dispatcher: Name of the dispatcher that executed this knot (e.g.
            ``'LocalDispatcher'``, ``'ThreadDispatcher'``).
        started_at: UTC wall-clock time when the knot began executing.
        finished_at: UTC wall-clock time when the knot finished (or failed).
        extra: Free-form metadata added by the framework or the knot itself,
            e.g. element index for knots inside a ``Map`` body, or the branch
            arm chosen by a ``Branch`` knot.
    """

    model_config = ConfigDict(frozen=True)

    # Identity
    run_id: str
    knot_id: str
    knot_class: str = Field(
        ...,
        description="Fully-qualified class name of the knot, e.g. "
        "'my_pkg.knots.EnrichUser'.  Used for cross-run filtering by kind.",
    )

    # Definition snapshot — what *this* knot looked like at run time.
    # Hashing the config makes 'has the knot's configuration changed since
    # the last run?' a one-line query.
    knot_config_hash: str

    # Wiring snapshot — content hashes of each named input.
    # Keys are the input parameter names on process(); values are hashes
    # of the value the parent supplied.  Empty for parameter-less knots.
    parent_input_hashes: dict[str, str] = Field(default_factory=dict)

    # The output's content hash, or None if the knot failed / was skipped.
    output_hash: str | None = None

    # Outcome — exactly one of these is set, except for skipped knots
    # which have neither output_hash nor error_record_id.
    outcome: str = Field(
        ...,
        description="One of 'ok', 'err', 'skipped'.",
    )
    error_record_id: str | None = Field(
        None,
        description="If outcome=='err', the run-scoped id of the "
        "ExceptionRecord registered with the run's ExceptionManager.",
    )
    skip_reason: str | None = Field(
        None,
        description="If outcome=='skipped', why.",
    )

    # Execution context.
    dispatcher: str = Field(
        ...,
        description="Name of the dispatcher that ran this knot, e.g. "
        "'LocalDispatcher', 'ThreadDispatcher'.",
    )

    # Timing.
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # Free-form metadata, e.g. element index for knots inside a Map body,
    # branch name chosen for Branch outputs, etc.
    extra: dict[str, Any] = Field(default_factory=dict)

    # Content-addressed reference to the knot's source code snapshot.
    # None when source was unavailable at capture time (compiled extensions,
    # dynamically exec-created classes, etc.).
    source_hash: str | None = None

    @property
    def duration_ms(self) -> float:
        return (self.finished_at - self.started_at).total_seconds() * 1000.0

    @property
    def succeeded(self) -> bool:
        return self.outcome == "ok"
