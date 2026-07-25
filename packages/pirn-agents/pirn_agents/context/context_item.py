"""``ContextItem`` — one unit of candidate context for token-budgeted assembly."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class ContextItem(PirnOpaqueValue):
    """A single piece of context competing for room in the token budget.

    The assembler treats messages, retrieved snippets, and tool results
    uniformly as items; the ``kind`` label is advisory metadata. The three
    eviction signals — ``position`` (recency), ``relevance``, and ``priority``
    (importance) — let a policy decide drop order; ``pinned`` items are never
    evicted.

    Attributes
    ----------
    content:
        The item's text, whose token cost is measured by the token counter.
    kind:
        Advisory category: ``"message"``, ``"retrieved"``, ``"tool_result"``,
        or any custom label.
    position:
        Recency ordinal — higher means more recent. Recency eviction drops the
        lowest positions first.
    relevance:
        Relevance score in any caller-defined scale — higher is more relevant.
        Relevance eviction drops the lowest scores first.
    priority:
        Importance rank — higher is more important. Importance eviction drops
        the lowest priorities first.
    pinned:
        When ``True`` the item is always retained, even if the budget is
        exceeded.
    """

    content: str
    kind: str = "message"
    position: int = 0
    relevance: float = 0.0
    priority: int = 0
    pinned: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.content, str):
            raise TypeError(
                f"ContextItem: content must be a str, got {type(self.content).__name__}"
            )
        if not isinstance(self.kind, str) or not self.kind:
            raise TypeError("ContextItem: kind must be a non-empty str")

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "kind": self.kind,
            "position": self.position,
            "relevance": self.relevance,
            "priority": self.priority,
            "pinned": self.pinned,
        }
