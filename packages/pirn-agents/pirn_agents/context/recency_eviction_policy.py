"""``RecencyEvictionPolicy`` — evict the oldest context items first."""

from __future__ import annotations

from pirn_agents.context.context_item import ContextItem
from pirn_agents.context.eviction_policy import EvictionPolicy


class RecencyEvictionPolicy(EvictionPolicy):
    """Drops the least-recent items first, keeping the freshest context.

    Ranks by ``position`` (higher means more recent), so the lowest positions —
    the oldest turns — are evicted first.
    """

    def eviction_rank(self, item: ContextItem) -> float:
        if not isinstance(item, ContextItem):
            raise TypeError(
                f"RecencyEvictionPolicy: item must be a ContextItem, got {type(item).__name__}"
            )
        return float(item.position)
