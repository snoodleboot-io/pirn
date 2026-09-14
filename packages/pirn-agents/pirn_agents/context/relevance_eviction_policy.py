"""``RelevanceEvictionPolicy`` — evict the least-relevant context items first."""

from __future__ import annotations

from pirn_agents.context.context_item import ContextItem
from pirn_agents.context.eviction_policy import EvictionPolicy


class RelevanceEvictionPolicy(EvictionPolicy):
    """Drops the least-relevant items first, keeping the most on-topic context.

    Ranks by ``relevance`` (higher is more relevant), so the lowest-scoring
    items are evicted first.
    """

    def eviction_rank(self, item: ContextItem) -> float:
        if not isinstance(item, ContextItem):
            raise TypeError(
                f"RelevanceEvictionPolicy: item must be a ContextItem, got {type(item).__name__}"
            )
        return float(item.relevance)
