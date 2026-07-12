"""``CompactionResult`` — the outcome of a compaction pass."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.context.context_item import ContextItem


@dataclass(frozen=True)
class CompactionResult(PirnOpaqueValue):
    """The result of compacting context.

    Attributes
    ----------
    retained:
        The post-compaction items in order: preserved (incl. pinned) content
        with a single summary item standing in for the compacted block.
    evicted:
        The original items that were summarized away, in eviction order.
    summary:
        The summary text produced for the evicted items (``""`` when nothing was
        compacted).
    summary_item:
        The synthetic pinned :class:`ContextItem` carrying the summary, or
        ``None`` when compaction did not trigger.
    triggered:
        Whether compaction actually ran (fill threshold exceeded *and* there was
        evictable content).
    tokens_before:
        Total token cost of the input items.
    tokens_after:
        Total token cost of the retained items.
    """

    retained: tuple[ContextItem, ...]
    evicted: tuple[ContextItem, ...]
    summary: str
    summary_item: ContextItem | None
    triggered: bool
    tokens_before: int
    tokens_after: int

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "retained": [item._pirn_audit_dict() for item in self.retained],
            "evicted": [item._pirn_audit_dict() for item in self.evicted],
            "summary": self.summary,
            "triggered": self.triggered,
            "tokens_before": self.tokens_before,
            "tokens_after": self.tokens_after,
        }
