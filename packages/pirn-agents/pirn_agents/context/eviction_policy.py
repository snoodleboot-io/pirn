"""``EvictionPolicy`` — the pluggable strategy that decides context drop order.

A policy exposes a single primitive — :meth:`eviction_rank`, mapping a
:class:`~pirn_agents.context.context_item.ContextItem` to a comparable rank
where **lower ranks are evicted first**. The assembler sorts evictable items by
that rank (stably, so ties keep their original order) and drops from the front
until the budget is met. Concrete recency / relevance / importance policies each
override only :meth:`eviction_rank`.
"""

from __future__ import annotations

from collections.abc import Sequence

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.context.context_item import ContextItem


class EvictionPolicy(PirnOpaqueValue):
    """Interface for context eviction policies."""

    def eviction_rank(self, item: ContextItem) -> float:
        """Return ``item``'s rank; lower ranks are evicted first."""
        raise NotImplementedError(f"{type(self).__name__} must implement eviction_rank()")

    def order_for_eviction(self, items: Sequence[ContextItem]) -> tuple[ContextItem, ...]:
        """Return ``items`` ordered by ascending eviction rank (drop-first first).

        The sort is stable, so items sharing a rank retain their input order.
        """
        return tuple(sorted(items, key=self.eviction_rank))
