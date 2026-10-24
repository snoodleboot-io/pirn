"""``ShortestPathResult`` — surface the finished path search as a node-id list.

The loop's output is its final :class:`PathSearchState`, which carries the live
store and the bounds alongside the answer. This knot narrows that to the part
callers consume.

Internal API. See ``graph_shortest_path.py``.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.retrieval.graph_rag.path_search_state import PathSearchState


class ShortestPathResult(Knot):
    """Extract the path a finished search found, if it found one."""

    def __init__(
        self,
        *,
        state: Knot | PathSearchState,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(state=state, _config=_config, **kwargs)

    async def process(self, state: PathSearchState, **_: Any) -> list[str] | None:
        """Return the node-id path, or ``None`` when none was found in budget.

        Args:
            state: The loop's final state.

        Returns:
            The path inclusive of both endpoints, or ``None``.
        """
        return list(state.found) if state.found is not None else None
