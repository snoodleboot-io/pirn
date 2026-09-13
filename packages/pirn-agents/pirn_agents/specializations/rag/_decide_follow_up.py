"""``_DecideFollowUp`` — ask the LLM whether more evidence is needed."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.llm.llm_provider import LLMProvider


class _DecideFollowUp(Knot):
    """Ask the LLM whether more evidence is needed, and for what query."""

    def __init__(
        self,
        *,
        original_query: Knot | str,
        current_query: Knot | str,
        merged: Knot | Mapping[str, Mapping[str, Any]],
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            original_query=original_query,
            current_query=current_query,
            merged=merged,
            llm=llm,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        original_query: str,
        current_query: str,
        merged: Mapping[str, Mapping[str, Any]],
        llm: LLMProvider,
        **_: Any,
    ) -> str | None:
        """Ask the LLM to refine; return a follow-up query or ``None`` to stop."""
        # Local import: avoids a cycle with iterative_retriever, which
        # imports the loop that imports this module.
        from pirn_agents.specializations.rag.iterative_retriever import IterativeRetriever

        return await IterativeRetriever._decide(llm, original_query, merged, current_query)
