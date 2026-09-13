"""``TraceDiffer`` — align two recorded runs and report what diverged."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pirn.knot_diff import compare_runs

from pirn_agents.determinism.run_trace import RunTrace
from pirn_agents.determinism.trace_diff import TraceDiff
from pirn_agents.determinism.trace_event import TraceEvent

if TYPE_CHECKING:
    from pirn.core.run_result import RunResult
    from pirn.knot_diff import KnotDiff


class TraceDiffer:
    """Compare two recorded runs and report what diverged.

    :meth:`diff` compares two :class:`RunTrace` values (from
    :class:`~pirn_agents.determinism.trajectory_recorder.TrajectoryRecorder`
    or an exported :class:`~pirn_agents.determinism.trajectory_emitter.TrajectoryEmitter`
    snapshot) step-by-step, aligned by index. :meth:`diff_runs` (ADR
    "agents speaks core" WS3 part 3) compares two ``RunResult``s directly via
    core's ``pirn.knot_diff.compare_runs``, aligned by knot id — the more
    precise comparison when both runs are real engine runs, since a step's
    identity is its knot id, not its position.
    """

    def diff_runs(self, left: RunResult, right: RunResult) -> list[KnotDiff]:
        """Return core's per-knot diff of ``left`` versus ``right``, by knot id.

        A thin pass-through to ``pirn.knot_diff.compare_runs`` — kept here so
        callers already depending on ``TraceDiffer`` for run comparison do
        not need a second import for the ``RunResult`` case.
        """
        return compare_runs(left, right)

    def diff(self, before: RunTrace, after: RunTrace) -> TraceDiff:
        """Return the :class:`TraceDiff` of ``before`` versus ``after``.

        Raises:
            TypeError: If either argument is not a RunTrace.
        """
        if not isinstance(before, RunTrace):
            raise TypeError(
                f"TraceDiffer.diff: before must be a RunTrace, got {type(before).__name__}"
            )
        if not isinstance(after, RunTrace):
            raise TypeError(
                f"TraceDiffer.diff: after must be a RunTrace, got {type(after).__name__}"
            )
        common = min(len(before.events), len(after.events))
        changed: list[dict[str, Any]] = []
        for index in range(common):
            entry = self._compare(before.events[index], after.events[index])
            if entry is not None:
                changed.append(entry)
        removed = tuple(range(common, len(before.events)))
        added = tuple(range(common, len(after.events)))
        return TraceDiff(changed=tuple(changed), added=added, removed=removed)

    @staticmethod
    def _compare(before: TraceEvent, after: TraceEvent) -> dict[str, Any] | None:
        """Return a change record for one aligned index, or ``None`` if identical."""
        fields: list[str] = []
        if before.kind is not after.kind:
            fields.append("kind")
        if before.name != after.name:
            fields.append("name")
        if before.digest != after.digest:
            fields.append("payload")
        if not fields:
            return None
        return {
            "index": before.index,
            "fields": fields,
            "before": before.to_payload(),
            "after": after.to_payload(),
        }
