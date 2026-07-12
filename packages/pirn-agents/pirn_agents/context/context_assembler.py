"""``ContextAssembler`` — fit mixed context items under a token budget.

Algorithm:
    1. Receive the resolved ``items``, ``budget``, ``counter``, and ``policy``.
    2. Validate input types at process time.
    3. Size every item once via the token counter (O(n)).
    4. If the total already fits the budget, keep everything (still O(n)).
    5. Otherwise sort only the *evictable* (non-pinned) items by the policy's
       eviction rank and drop from the front until the total fits; pinned items
       are never dropped.
    6. Return an :class:`AssembledContext` with kept items (original order),
       evicted items (eviction order), and the kept total token count.

Complexity is O(n) in the common fits-the-budget path and O(n log n) only when
eviction is required (a single sort of the evictable items).


References:
    - :class:`pirn_agents.context.context_item.ContextItem`
    - :class:`pirn_agents.context.context_budget.ContextBudget`
    - :class:`pirn_agents.context.eviction_policy.EvictionPolicy`
    - :class:`pirn_agents.context.token_counter.TokenCounter`
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.context.assembled_context import AssembledContext
from pirn_agents.context.context_budget import ContextBudget
from pirn_agents.context.context_item import ContextItem
from pirn_agents.context.eviction_policy import EvictionPolicy
from pirn_agents.context.recency_eviction_policy import RecencyEvictionPolicy
from pirn_agents.context.token_counter import TokenCounter


class ContextAssembler(Knot):
    """Assembles context items to fit a token budget with pluggable eviction."""

    def __init__(
        self,
        *,
        items: Knot | Sequence[ContextItem],
        budget: Knot | ContextBudget | int,
        counter: Knot | TokenCounter,
        _config: KnotConfig,
        policy: Knot | EvictionPolicy | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            items=items,
            budget=budget,
            counter=counter,
            policy=policy,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        items: Sequence[ContextItem],
        budget: ContextBudget | int,
        counter: TokenCounter,
        policy: EvictionPolicy | None = None,
        **_: Any,
    ) -> AssembledContext:
        """Fit ``items`` under ``budget``, evicting non-pinned items by ``policy``.

        Args:
            items: Candidate context items (messages/retrieved/tool results).
            budget: A :class:`ContextBudget` or a plain integer token ceiling.
            counter: The token counter used to size each item's content.
            policy: The eviction policy; defaults to recency when ``None``.

        Returns:
            An :class:`AssembledContext` of kept items, evicted items, and the
            kept total token count.

        Raises:
            TypeError: If any argument is of the wrong type.
            ValueError: If an integer budget is negative.
        """
        resolved_policy = policy if policy is not None else RecencyEvictionPolicy()
        self._validate(items, counter, resolved_policy)
        available = self._resolve_budget(budget)

        sizes = [counter.count(item.content) for item in items]
        total = sum(sizes)
        if total <= available:
            return AssembledContext(kept=tuple(items), evicted=(), total_tokens=total)

        evictable = [index for index, item in enumerate(items) if not item.pinned]
        ordered = sorted(
            evictable, key=lambda index: (resolved_policy.eviction_rank(items[index]), index)
        )
        dropped: set[int] = set()
        running = total
        for index in ordered:
            if running <= available:
                break
            dropped.add(index)
            running -= sizes[index]

        kept = tuple(item for index, item in enumerate(items) if index not in dropped)
        evicted = tuple(items[index] for index in ordered if index in dropped)
        return AssembledContext(kept=kept, evicted=evicted, total_tokens=running)

    @staticmethod
    def _validate(
        items: Sequence[ContextItem],
        counter: TokenCounter,
        policy: EvictionPolicy,
    ) -> None:
        """Validate the item sequence, counter, and policy types."""
        if not isinstance(items, Sequence) or isinstance(items, (str, bytes)):
            raise TypeError(
                f"ContextAssembler: items must be a sequence, got {type(items).__name__}"
            )
        for index, item in enumerate(items):
            if not isinstance(item, ContextItem):
                raise TypeError(
                    f"ContextAssembler: items[{index}] must be a ContextItem, "
                    f"got {type(item).__name__}"
                )
        if not isinstance(counter, TokenCounter):
            raise TypeError(
                f"ContextAssembler: counter must be a TokenCounter, got {type(counter).__name__}"
            )
        if not isinstance(policy, EvictionPolicy):
            raise TypeError(
                f"ContextAssembler: policy must be an EvictionPolicy, got {type(policy).__name__}"
            )

    @staticmethod
    def _resolve_budget(budget: ContextBudget | int) -> int:
        """Return the available token room from a ``ContextBudget`` or int."""
        if isinstance(budget, ContextBudget):
            return budget.available()
        if isinstance(budget, bool) or not isinstance(budget, int):
            raise TypeError(
                f"ContextAssembler: budget must be a ContextBudget or int, "
                f"got {type(budget).__name__}"
            )
        if budget < 0:
            raise ValueError(f"ContextAssembler: budget must be non-negative, got {budget!r}")
        return budget
