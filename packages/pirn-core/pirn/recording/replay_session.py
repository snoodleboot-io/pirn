"""``ReplaySession`` — a recorded run, indexed so the engine can serve from it."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pirn.core.err import Err
from pirn.core.lineage import KnotLineage
from pirn.core.ok import Ok
from pirn.core.result import Result
from pirn.core.skipped import Skipped
from pirn.managers.exception_record import ExceptionRecord
from pirn.recording.invocation_identity import InvocationIdentity
from pirn.recording.replay_mismatch_error import ReplayMismatchError
from pirn.recording.replay_value_unavailable_error import ReplayValueUnavailableError

if TYPE_CHECKING:
    from pirn.backends.base.data_store import DataStore
    from pirn.backends.base.run_history import RunHistory
    from pirn.core.knot import Knot
    from pirn.core.run_result import RunResult


class ReplaySession:
    """A past run, indexed by knot id, that a new run can be served from.

    Pass one to ``Tapestry.run(request, replay=session)`` to put that run in
    replay posture: each knot's recorded outcome is resolved from this
    session's lineage and the tapestry's ``DataStore`` instead of being
    executed.  A knot with a side effect — a network call, a counter, a write
    — does not run at all.

    There is no matching *record* posture because core already records
    unconditionally: every run writes a ``KnotLineage`` row per knot and puts
    every ``Ok`` value into the ``DataStore`` under its content hash.  The
    three-way record/replay/passthrough posture that hand-rolled cassettes
    need collapses, in core, to "replay or not".  What is not automatic is
    *durability*: the default ``InMemoryDataStore`` discards the recording
    with the process, so a recording meant to outlive the run needs a durable
    ``data_store=`` on the ``Tapestry``.

    Identity and matching
    ---------------------
    Within a run, ``knot_id`` is unique — the engine dispatches each knot in
    the shed exactly once and writes exactly one lineage row for it, including
    for knots that fan out over a ``Map``/``ZipMap``/``DictMap`` input (the
    per-element calls happen *inside* one invocation, whose single output is
    the whole list).  ``knot_id`` is therefore the index, and the hashes
    ``KnotLineage`` records are the *guard*: a row is honoured only if its
    ``knot_config_hash``, ``parent_input_hashes`` and recorded
    ``config_values_hash`` all agree with what this run is about to feed the
    knot.  Anything else raises ``ReplayMismatchError``.

    ``Parameter`` knots are the deliberate exception: they always execute.
    Their value comes from the ``RunRequest``, not from a parent, and
    ``KnotConfig`` does not carry it — a parameter bound to ``1`` and one
    bound to ``99`` record byte-identical config hashes and identically empty
    input hashes.  Replaying them by substitution would silently ignore the
    parameters the caller just supplied.  Instead they are bound and run as
    usual and their output hash is checked against the recording, so a
    changed parameter fails loudly at the parameter itself rather than
    corrupting everything downstream of it.

    Attributes:
        source_run_id: The ``run_id`` this session serves from.
    """

    def __init__(self, *, source_run: RunResult) -> None:
        """Index a ``RunResult`` for replay.

        Prefer :meth:`from_history`, which loads the run for you.

        Args:
            source_run: The completed run to serve recorded outcomes from.
        """
        self._source_run_id: str = source_run.run_id
        self._rows: dict[str, KnotLineage] = {row.knot_id: row for row in source_run.lineage}
        self._exceptions: dict[str, ExceptionRecord] = {
            record.id: record for record in source_run.exceptions
        }

    @classmethod
    async def from_history(cls, *, history: RunHistory, run_id: str) -> ReplaySession:
        """Load a recorded run from *history* and index it for replay.

        Args:
            history: The ``RunHistory`` the original run was recorded to.
            run_id: The run to replay.

        Returns:
            A ``ReplaySession`` over that run.

        Raises:
            KeyError: If *run_id* is not present in *history*.
        """
        source_run: RunResult | None = await history.get_run(run_id)
        if source_run is None:
            raise KeyError(f"run {run_id!r} not found in history; cannot replay it")
        return cls(source_run=source_run)

    @property
    def source_run_id(self) -> str:
        return self._source_run_id

    def row_for(self, knot_id: str) -> KnotLineage | None:
        """Return the recorded lineage row for *knot_id*, or ``None``."""
        return self._rows.get(knot_id)

    def verify_executed(self, *, knot_id: str, output_hash: str) -> None:
        """Check a knot that replay executed anyway against the recording.

        Used for ``Parameter`` knots, which replay binds and runs rather than
        substitutes.

        Args:
            knot_id: The knot that executed.
            output_hash: Content hash of the value it produced.

        Raises:
            ReplayMismatchError: If the recording has no row for *knot_id*, or
                records a different output hash.
        """
        row = self._require_row(knot_id)
        if row.output_hash != output_hash:
            raise ReplayMismatchError(
                knot_id=knot_id,
                source_run_id=self._source_run_id,
                reason=(
                    f"the recorded run produced output hash {row.output_hash!r} here "
                    f"but this run produced {output_hash!r} — the supplied value "
                    "differs from the one that was recorded"
                ),
            )

    async def resolve(
        self,
        *,
        knot: Knot,
        knot_config_hash: str,
        parent_input_hashes: dict[str, str],
        data_store: DataStore,
    ) -> Result[Any]:
        """Return the recorded outcome for *knot* without executing it.

        Args:
            knot: The knot this run was about to dispatch.
            knot_config_hash: Hash of the knot's config, as the engine
                computes it for the lineage row.
            parent_input_hashes: Content hashes of the values this run
                resolved for the knot's parents.
            data_store: Where the recorded value is read from.

        Returns:
            ``Ok`` carrying the recorded value, ``Skipped`` carrying the
            recorded reason, or ``Err`` carrying a rebindable copy of the
            recorded exception.

        Raises:
            ReplayMismatchError: If the recording does not describe this
                invocation.
            ReplayValueUnavailableError: If it does, but the value is no
                longer in *data_store*.
        """
        knot_id = knot.knot_id
        row = self._require_row(knot_id)
        self._require_match(row=row, knot=knot, knot_config_hash=knot_config_hash)
        self._require_inputs_match(row=row, parent_input_hashes=parent_input_hashes)

        if row.outcome == "skipped":
            return Skipped(reason=row.skip_reason or "replayed_skip")
        if row.outcome == "err":
            return Err(record=self._replayed_exception(row))

        output_hash = row.output_hash
        if output_hash is None:
            raise ReplayMismatchError(
                knot_id=knot_id,
                source_run_id=self._source_run_id,
                reason=(
                    f"the recorded row has outcome {row.outcome!r} but no output hash, "
                    "so there is nothing to serve"
                ),
            )
        if not await data_store.has(output_hash):
            raise ReplayValueUnavailableError(
                knot_id=knot_id,
                source_run_id=self._source_run_id,
                output_hash=output_hash,
            )
        return Ok(value=await data_store.get(output_hash))

    # ------------------------------------------------------------- internals

    def _require_row(self, knot_id: str) -> KnotLineage:
        row = self._rows.get(knot_id)
        if row is None:
            raise ReplayMismatchError(
                knot_id=knot_id,
                source_run_id=self._source_run_id,
                reason=(
                    "the recorded run has no lineage row for this knot — it was "
                    "added to the tapestry after the recording, or the recording "
                    "ran a different set of terminals"
                ),
            )
        return row

    def _require_match(self, *, row: KnotLineage, knot: Knot, knot_config_hash: str) -> None:
        if row.knot_config_hash != knot_config_hash:
            raise ReplayMismatchError(
                knot_id=knot.knot_id,
                source_run_id=self._source_run_id,
                reason=(
                    f"knot config hash changed since the recording "
                    f"({row.knot_config_hash!r} -> {knot_config_hash!r})"
                ),
            )
        recorded_literals = row.extra.get("config_values_hash")
        current_literals = InvocationIdentity.config_values_hash(knot)
        if recorded_literals != current_literals:
            raise ReplayMismatchError(
                knot_id=knot.knot_id,
                source_run_id=self._source_run_id,
                reason=(
                    f"the knot's literal constructor arguments changed since the "
                    f"recording ({recorded_literals!r} -> {current_literals!r})"
                ),
            )

    def _require_inputs_match(
        self,
        *,
        row: KnotLineage,
        parent_input_hashes: dict[str, str],
    ) -> None:
        if row.parent_input_hashes == parent_input_hashes:
            return
        raise ReplayMismatchError(
            knot_id=row.knot_id,
            source_run_id=self._source_run_id,
            reason=(
                f"parent input hashes differ from the recording "
                f"(recorded {row.parent_input_hashes!r}, this run {parent_input_hashes!r})"
            ),
        )

    def _replayed_exception(self, row: KnotLineage) -> ExceptionRecord:
        """Rebuild the recorded failure as an unbound placeholder record.

        The engine re-registers it with this run's ``ExceptionManager``, so the
        replayed run reports the same failure under its own run id.
        """
        recorded = self._exceptions.get(row.error_record_id or "")
        if recorded is None:
            return ExceptionRecord(
                run_id="<unbound>",
                knot_id=row.knot_id,
                exc_type="ReplayedError",
                message=(
                    f"knot {row.knot_id!r} failed in recorded run "
                    f"{self._source_run_id!r}; the exception record was not retained"
                ),
                traceback_text="",
            )
        return ExceptionRecord(
            run_id="<unbound>",
            knot_id=row.knot_id,
            exc_type=recorded.exc_type,
            message=recorded.message,
            traceback_text=recorded.traceback_text,
        )
