"""Run replay and diff utilities.

``replay_run`` re-executes a past run against a tapestry, optionally
overriding parameters.  ``compare_runs`` diffs two results knot-by-knot
by output hash.

Typical workflow::

    from pirn import replay_run, compare_runs
    from pirn.backends.sqlite import SQLiteHistory

    history = SQLiteHistory("pirn.db")
    t = build_tapestry(history=history)

    # Original run
    result = await t.run(RunRequest(parameters={"x": 1, "y": 2}))

    # Replay with one parameter changed
    new_result = await replay_run(
        history=history,
        run_id=result.run_id,
        tapestry=t,
        base_parameters={"x": 1, "y": 2},
        parameter_overrides={"y": 99},
    )

    # See what changed
    for diff in compare_runs(result, new_result):
        if diff.changed:
            print(diff)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pirn.backends import RunHistory
    from pirn.core.context import RunResult
    from pirn.tapestry import Tapestry


@dataclass(frozen=True)
class KnotDiff:
    """Per-knot comparison between two runs."""

    knot_id: str
    left_outcome: str | None  # outcome in the first run, or None if absent
    right_outcome: str | None  # outcome in the second run, or None if absent
    left_hash: str | None  # output_hash in the first run
    right_hash: str | None  # output_hash in the second run

    @property
    def changed(self) -> bool:
        """True if the knot produced a different output or a different outcome."""
        return self.left_hash != self.right_hash or self.left_outcome != self.right_outcome

    @property
    def outcome_changed(self) -> bool:
        return self.left_outcome != self.right_outcome

    @property
    def output_changed(self) -> bool:
        return self.left_hash != self.right_hash

    def __str__(self) -> str:
        outcome_note = ""
        if self.outcome_changed:
            outcome_note = f" [{self.left_outcome} → {self.right_outcome}]"
        if self.output_changed:
            return f"~ {self.knot_id}{outcome_note} (hash changed)"
        if self.outcome_changed:
            return f"~ {self.knot_id}{outcome_note}"
        return f"= {self.knot_id}"


async def replay_run(
    *,
    history: RunHistory,
    run_id: str,
    tapestry: Tapestry,
    base_parameters: dict[str, Any],
    parameter_overrides: dict[str, Any] | None = None,
    new_run_id: str | None = None,
) -> RunResult:
    """Re-execute a past run against *tapestry*, optionally overriding parameters.

    Verifies the original run exists in *history*, then executes a new run
    with *base_parameters* merged with *parameter_overrides*.

    Parameters are not stored in ``RunResult`` (they live in the original
    ``RunRequest`` which the caller retains), so the caller must supply
    *base_parameters*.  Use *parameter_overrides* to change individual values
    without restating the full set.

    Args:
        history: The ``RunHistory`` that stored the original run.
        run_id: ID of the run to replay (verified to exist in history).
        tapestry: The tapestry to execute against.
        base_parameters: The original parameter set to replay from.
        parameter_overrides: Parameter values to change for the replay.
            Merged on top of *base_parameters*.
        new_run_id: Override the auto-generated run id for the replay.

    Returns:
        The ``RunResult`` for the replayed run.

    Raises:
        KeyError: If *run_id* is not found in *history*.
    """
    from pirn.core.context import RunRequest

    original: RunResult = await history.get_run(run_id)
    if original is None:
        raise KeyError(f"run {run_id!r} not found in history")

    params: dict[str, Any] = dict(base_parameters)
    if parameter_overrides:
        params.update(parameter_overrides)

    if new_run_id is not None:
        request = RunRequest(parameters=params, run_id=new_run_id)
    else:
        request = RunRequest(parameters=params)
    return await tapestry.run(request)


def compare_runs(left: RunResult, right: RunResult) -> list[KnotDiff]:
    """Diff two ``RunResult`` objects knot-by-knot by output hash.

    Returns one ``KnotDiff`` per knot that appears in either run, sorted
    by knot id.  Knots present in only one run have ``None`` for the missing
    side.

    Args:
        left: The first (typically original) run.
        right: The second (typically replayed) run.

    Returns:
        List of ``KnotDiff`` records, one per knot, sorted by knot_id.
    """
    left_map = {rec.knot_id: rec for rec in left.lineage}
    right_map = {rec.knot_id: rec for rec in right.lineage}
    all_ids = sorted(left_map.keys() | right_map.keys())

    return [
        KnotDiff(
            knot_id=knot_id,
            left_outcome=left_map[knot_id].outcome if knot_id in left_map else None,
            right_outcome=right_map[knot_id].outcome if knot_id in right_map else None,
            left_hash=left_map[knot_id].output_hash if knot_id in left_map else None,
            right_hash=right_map[knot_id].output_hash if knot_id in right_map else None,
        )
        for knot_id in all_ids
    ]
