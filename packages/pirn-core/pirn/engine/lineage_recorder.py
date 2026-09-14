"""``LineageRecorder`` — builds and stashes a ``KnotLineage`` per knot execution.

Extracted out of ``Engine`` (a pure move, PIR-856): neither method reads or
writes any ``Engine`` instance state (both take everything they need as
arguments), so both are ``@staticmethod``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from pirn.core.content_hasher import ContentHasher
from pirn.core.err import Err
from pirn.core.knot_lineage import KnotLineage
from pirn.core.knot_source_record import KnotSourceRecord
from pirn.core.ok import Ok
from pirn.core.skipped import Skipped
from pirn.recording.invocation_identity import InvocationIdentity

if TYPE_CHECKING:
    from pirn.core.knot import Knot
    from pirn.core.result import Result
    from pirn.core.run_context import RunContext


class LineageRecorder:
    """Stateless helpers that build and stash a ``KnotLineage`` record."""

    @staticmethod
    def config_hash(knot: Knot) -> str:
        """Hash the knot's canonical config — the value lineage records."""
        return ContentHasher.hash(knot.config.model_dump(mode="json"))

    @staticmethod
    def record_lineage(
        ctx: RunContext,
        knot: Knot,
        results: dict[str, Result[Any]],
        result: Result[Any],
        parent_hashes: dict[str, str] | None = None,
        started: datetime | None = None,
        finished: datetime | None = None,
        replayed_from: str | None = None,
    ) -> KnotLineage:
        """Build and stash a KnotLineage for this knot's execution.

        For knots that didn't actually dispatch (Skipped / synthetic Err),
        ``parent_hashes`` is computed here from the available parent
        results.

        ``finished`` is when the knot's outcome came into existence; it
        defaults to now, which is exact for a knot resolved without dispatch.

        ``replayed_from`` is the run id this outcome was served from when the
        knot was replayed rather than executed; it lands in ``extra`` so a
        replayed run is distinguishable from a live one after the fact.

        Returns:
            The record just stashed on ``ctx``, so the engine can hand it to
            ``Emitter.on_knot_result`` the moment the knot settles (WS0b).
        """
        if parent_hashes is None:
            parent_hashes = {}
            # Recompute from the actual result map for knots that did
            # not dispatch (Skipped / synthetic Err).
            for parent_name, parent_knot in knot.parents.items():
                pr = results.get(parent_knot.knot_id)
                if pr is not None:
                    parent_hashes[parent_name] = ContentHasher.hash(
                        pr.value if isinstance(pr, Ok) else pr
                    )

        if isinstance(result, Ok):
            outcome = "ok"
            output_hash = ContentHasher.hash(result.value)
            error_record_id = None
            skip_reason = None
        elif isinstance(result, Err):
            outcome = "err"
            output_hash = None
            error_record_id = result.record.id
            skip_reason = None
        else:  # Skipped
            outcome = "skipped"
            output_hash = None
            error_record_id = None
            skip_reason = result.reason

        # If validate_io is on, we hash the canonical config (the user-
        # facing fields).  Otherwise we hash a sentinel.
        cfg_hash = LineageRecorder.config_hash(knot)

        parent_knot_ids = {name: pk.knot_id for name, pk in knot.parents.items()}

        pirn_version = ctx.runtime_info.get("pirn_version", "unknown")
        source_record = KnotSourceRecord.from_knot(knot, pirn_version)
        if source_record is not None:
            ctx.add_knot_source(source_record)

        extra: dict[str, Any] = {"parent_knot_ids": parent_knot_ids} if parent_knot_ids else {}

        # Merge structured execution context contributed by the knot itself.
        extra.update(knot.lineage_extra())

        # L-4: Optional knot — Ok(Skipped) means the knot ran but produced Skipped.
        if isinstance(result, Ok) and isinstance(result.value, Skipped):
            skip_info: dict[str, Any] = {"reason": result.value.reason}
            if result.value.detail:
                skip_info.update(result.value.detail)
            extra["optional_skip"] = skip_info

        # A skip whose reason downstream skips inherit (a Gate closed by a
        # Check naming its own skip_reason) says so, so a replay serves the
        # same propagation (PIR-872).
        if isinstance(result, Skipped) and result.propagates:
            extra["skip_propagates"] = True

        # L-7: Record the applied error policy.
        extra["error_policy"] = str(knot.config.error_policy)

        # Literal constructor arguments reach process() as inputs but are
        # covered by neither ``knot_config_hash`` nor ``parent_input_hashes``.
        # Record their hash so a reader can tell ``Scale(x=p, factor=3)`` from
        # ``Scale(x=p, factor=5)``, which are otherwise byte-identical in
        # lineage (PIR-836).  ``None`` when the knot has no literal inputs.
        config_values_hash = InvocationIdentity.config_values_hash(knot)

        if replayed_from is not None:
            extra["replayed_from_run_id"] = replayed_from

        record = KnotLineage(
            run_id=ctx.run_id,
            knot_id=knot.knot_id,
            knot_class=f"{type(knot).__module__}.{type(knot).__qualname__}",
            knot_config_hash=cfg_hash,
            config_values_hash=config_values_hash,
            parent_input_hashes=parent_hashes,
            output_hash=output_hash,
            outcome=outcome,
            error_record_id=error_record_id,
            skip_reason=skip_reason,
            dispatcher=ctx.dispatcher_name,
            started_at=started or ctx.started_at,
            finished_at=finished or datetime.now(UTC),
            extra=extra,
            source_hash=source_record.source_hash if source_record is not None else None,
        )
        ctx.add_lineage(record)
        return record
