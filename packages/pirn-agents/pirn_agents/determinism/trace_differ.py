"""``TraceDiffer`` — align two recorded runs and report what diverged."""

from __future__ import annotations

from typing import Any

from pirn_agents.determinism.run_trace import RunTrace
from pirn_agents.determinism.trace_diff import TraceDiff
from pirn_agents.determinism.trace_event import TraceEvent


class TraceDiffer:
    """Compare two :class:`RunTrace` values step-by-step into a :class:`TraceDiff`.

    Steps are aligned by index; a step is *changed* when its ``kind``, ``name`` or
    content ``digest`` differs, so a payload edit between prompt/model versions
    surfaces without a brittle raw-value comparison. Length differences become
    ``added`` / ``removed`` indices.
    """

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
