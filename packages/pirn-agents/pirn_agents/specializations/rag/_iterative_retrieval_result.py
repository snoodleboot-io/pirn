"""``_IterativeRetrievalResult`` — extract accumulated documents from state."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.specializations.rag._iterative_retrieval_state import _IterativeRetrievalState


class _IterativeRetrievalResult(Knot):
    """Extract the accumulated document list from the loop's final state."""

    def __init__(
        self,
        *,
        state: Knot | _IterativeRetrievalState,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(state=state, _config=_config, **kwargs)

    async def process(self, state: _IterativeRetrievalState, **_: Any) -> list[Mapping[str, Any]]:
        """Return the deduplicated union of documents accumulated across rounds."""
        return list(state.merged.values())
