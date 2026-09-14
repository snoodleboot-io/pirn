"""``LatsResultExtractor`` — surface the search's :class:`LatsResult`.

Replaces the inline ``_LatsResultSource(Source)`` that closed over an
already-computed :class:`LatsResult` (ADR agents-speaks-core WS5b;
PIR-856's imperative-loop inventory: a "returns inline Source" bypass). Pure
extraction — no LLM/tool call here.

Internal API. See PIR-856.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.specializations.lats.lats_node import LatsNode
from pirn_agents.specializations.lats.lats_result import LatsResult


class LatsResultExtractor(Knot):
    """Wrap the already-computed search outcome as a :class:`LatsResult`."""

    def __init__(
        self,
        *,
        best: LatsNode,
        nodes_expanded: int,
        budget_exhausted: bool,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            best=best,
            nodes_expanded=nodes_expanded,
            budget_exhausted=budget_exhausted,
            _config=_config,
            **kwargs,
        )

    async def process(
        self, best: LatsNode, nodes_expanded: int, budget_exhausted: bool, **_: Any
    ) -> LatsResult:
        """Return the :class:`LatsResult` for the whole search.

        Args:
            best: The highest-value node seen across the search.
            nodes_expanded: How many frontier nodes were popped and processed.
            budget_exhausted: Whether the search stopped because the budget
                meter raised, rather than the frontier emptying naturally.

        Returns:
            The :class:`LatsResult`.
        """
        return LatsResult(
            best_trajectory=best.trajectory,
            best_value=best.value,
            nodes_expanded=nodes_expanded,
            budget_exhausted=budget_exhausted,
        )
