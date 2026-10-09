"""``TraversalSubgraph`` — surface the finished traversal as a :class:`Subgraph`.

The loop's output is its final :class:`TraversalState`, which carries the live
store and the bounds alongside the result. This knot narrows that to the part
callers consume, the same way
:class:`~pirn_agents.specializations.lats.lats_result_extractor.LatsResultExtractor`
narrows a finished search.

Internal API. See ``graph_traversal.py``.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.retrieval.graph_rag.subgraph import Subgraph
from pirn_agents.retrieval.graph_rag.traversal_state import TraversalState


class TraversalSubgraph(Knot):
    """Extract the collected nodes and edges from a finished traversal."""

    def __init__(
        self,
        *,
        state: Knot | TraversalState,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(state=state, _config=_config, **kwargs)

    async def process(self, state: TraversalState, **_: Any) -> Subgraph:
        """Return the traversal's nodes and edges.

        Args:
            state: The loop's final state.

        Returns:
            The collected :class:`Subgraph`. Every recorded edge connects two
            collected nodes, so the selection is internally consistent.
        """
        return Subgraph(nodes=state.nodes, edges=state.edges)
