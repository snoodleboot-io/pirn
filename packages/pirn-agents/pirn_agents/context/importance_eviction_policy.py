"""``ImportanceEvictionPolicy`` — evict the least-important context items first."""

from __future__ import annotations

from pirn_agents.context.context_item import ContextItem
from pirn_agents.context.eviction_policy import EvictionPolicy


class ImportanceEvictionPolicy(EvictionPolicy):
    """Drops the lowest-priority items first, keeping the most important context.

    Ranks by ``priority`` (higher is more important), so the lowest-priority
    items are evicted first.
    """

    def eviction_rank(self, item: ContextItem) -> float:
        if not isinstance(item, ContextItem):
            raise TypeError(
                f"ImportanceEvictionPolicy: item must be a ContextItem, got {type(item).__name__}"
            )
        return float(item.priority)
