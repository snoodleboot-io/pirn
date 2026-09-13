"""``_FollowUpDecision`` — ask the LLM whether the tool's answer suffices."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.tools.tool_result import ToolResult


class _FollowUpDecision(Knot):
    """Ask the LLM whether the tool's answer resolves the original question."""

    def __init__(
        self,
        *,
        original_query: Knot | str,
        tool_result: Knot | ToolResult,
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            original_query=original_query,
            tool_result=tool_result,
            llm=llm,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        original_query: str,
        tool_result: ToolResult,
        llm: LLMProvider,
        **_: Any,
    ) -> str | None:
        """Ask the LLM for a follow-up question, or ``None`` when the answer suffices."""
        # Local import: avoids a cycle with agentic_rag_pipeline, which
        # imports the loop that imports this module.
        from pirn_agents.specializations.rag.agentic_rag_pipeline import AgenticRagPipeline

        answer = AgenticRagPipeline._tool_answer(tool_result.result)
        return await AgenticRagPipeline._next_question(llm, original_query, answer)
