"""``CompactionRequest`` — the input bundle for a compaction pass.

Bundling the inputs into one stable value is what makes
:class:`~pirn_agents.context.compaction_strategy.CompactionStrategy` a durable
seam: F27 (summary memory) can add new strategies that accept exactly this
request without any caller change.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.context.context_budget import ContextBudget
from pirn_agents.context.context_item import ContextItem
from pirn_agents.context.token_counter import TokenCounter


@dataclass(frozen=True)
class CompactionRequest(PirnOpaqueValue):
    """Everything a compaction strategy needs for one pass.

    Attributes
    ----------
    items:
        The current context items, oldest-to-newest by intent (``position``
        breaks ties when selecting what to compact).
    budget:
        A :class:`ContextBudget` or integer token ceiling the compacted context
        should fit.
    counter:
        The token counter used to measure fill.
    fill_threshold:
        Fraction of the available budget (``0 < t <= 1``) at which compaction
        triggers. Below it, the request is a no-op.
    persist_key:
        Optional key under which a strategy may persist the produced summary to
        its memory store (F27 integration point).
    """

    items: tuple[ContextItem, ...]
    budget: ContextBudget | int
    counter: TokenCounter
    fill_threshold: float = 0.8
    persist_key: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.items, tuple):
            raise TypeError("CompactionRequest: items must be a tuple of ContextItem")
        for index, item in enumerate(self.items):
            if not isinstance(item, ContextItem):
                raise TypeError(
                    f"CompactionRequest: items[{index}] must be a ContextItem, "
                    f"got {type(item).__name__}"
                )
        if not isinstance(self.counter, TokenCounter):
            raise TypeError("CompactionRequest: counter must be a TokenCounter")
        if isinstance(self.budget, bool) or not isinstance(self.budget, (ContextBudget, int)):
            raise TypeError("CompactionRequest: budget must be a ContextBudget or int")
        if not isinstance(self.fill_threshold, (int, float)) or not 0 < self.fill_threshold <= 1:
            raise ValueError(
                f"CompactionRequest: fill_threshold must be in (0, 1], got {self.fill_threshold!r}"
            )

    def available_tokens(self) -> int:
        """Return the available token room from the budget."""
        if isinstance(self.budget, ContextBudget):
            return self.budget.available()
        return self.budget

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "items": [item._pirn_audit_dict() for item in self.items],
            "available_tokens": self.available_tokens(),
            "fill_threshold": self.fill_threshold,
            "persist_key": self.persist_key,
        }
