"""``CompactionFrame`` — run-level facts of a compaction pass."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.context.context_item import ContextItem


@dataclass(frozen=True)
class CompactionFrame(PirnOpaqueValue):
    """What a compaction pass did, as opposed to what it retained.

    The frame half of the ``Payload[CompactionFrame, tuple[ContextItem, ...]]``
    split (PIR-868, PIR-874).

    Attributes
    ----------
    triggered:
        Whether compaction actually ran (fill threshold exceeded *and* there was
        evictable content).
    tokens_before:
        Total token cost of the input items.
    tokens_after:
        Total token cost of the retained items.
    summary:
        The summary text produced for the evicted items (``""`` when nothing was
        compacted).
    summary_item:
        The synthetic pinned :class:`ContextItem` carrying the summary, or
        ``None`` when compaction did not trigger.
    evicted:
        The original items that were summarized away, in eviction order.
    """

    triggered: bool
    tokens_before: int
    tokens_after: int
    summary: str
    summary_item: ContextItem | None
    evicted: tuple[ContextItem, ...]

    @staticmethod
    def _audit_all(values: tuple[PirnOpaqueValue, ...]) -> list[Any]:
        """Audit each child through the ``PirnOpaqueValue`` contract it shares with this value."""
        return [value._pirn_audit_dict() for value in values]

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "triggered": self.triggered,
            "tokens_before": self.tokens_before,
            "tokens_after": self.tokens_after,
            "summary": self.summary,
            "summary_item": (
                self._audit_all((self.summary_item,))[0] if self.summary_item is not None else None
            ),
            "evicted": self._audit_all(self.evicted),
        }
