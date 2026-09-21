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

from pirn_agents.specializations.lats.lats_result import LatsResult
from pirn_agents.specializations.lats.lats_search_state import LatsSearchState


class LatsResultExtractor(Knot):
    """Wrap the already-computed search outcome as a :class:`LatsResult`."""

    def __init__(
        self,
        *,
        state: Knot | LatsSearchState,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(state=state, _config=_config, **kwargs)

    async def process(self, state: LatsSearchState, **_: Any) -> LatsResult:
        """Return the :class:`LatsResult` for the whole search.

        Args:
            state: The search loop's final accumulated state — its ``best`` node,
                how many frontier nodes were popped, and whether the budget
                stopped the search rather than the frontier emptying.

        Returns:
            The :class:`LatsResult`.
        """
        best = state.best
        nodes_expanded = state.nodes_expanded
        budget_exhausted = state.budget_exhausted
        return LatsResult(
            best_trajectory=best.trajectory,
            best_value=best.value,
            nodes_expanded=nodes_expanded,
            budget_exhausted=budget_exhausted,
        )
