"""``AgenticRagPipeline`` — RAG exposed as a tool the agent drives in a loop.

Agentic RAG treats retrieval as an explicit, agent-callable action rather than a
fixed pipeline stage: the F6 :class:`~pirn_agents.tools.retrieval.rag_tool.RagTool`
is invoked, its answer is inspected, and — while a budget remains — the LLM may
issue a follow-up question that drives another tool call. The ``rag_tool`` is
validated as a standard :class:`~pirn_agents.tool.Tool` (isinstance) and called
exactly like any other tool in the loop.

Algorithm:
    1. Validate ``query`` (str), ``rag_tool`` (:class:`Tool`), ``llm``
       (:class:`LLMProvider`), and ``max_iterations`` (positive int).
    2. Start with ``current_question = query``. Repeat up to ``max_iterations``:
       a. ``await rag_tool.invoke({"question": current_question})`` and read the
          ``answer``.
       b. On the final allowed iteration, finalise with that answer.
       c. Otherwise ask the LLM to reply ``DONE`` (answer is sufficient) or
          ``FOLLOWUP: <next question>``; on ``FOLLOWUP`` loop, else finalise.
    3. Return the final answer as an :class:`AgentResponse`.

References:
    - Yao et al., "ReAct" (2022): https://arxiv.org/abs/2210.03629
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.providers.llm_provider import LLMProvider
from pirn.nodes.source import Source
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_agents.tool import Tool
from pirn_agents.types.agent_response import AgentResponse


class AgenticRagPipeline(SubTapestry):
    """Drive the RAG tool in a bounded agent loop, refining the question."""

    def __init__(
        self,
        *,
        query: Knot | str,
        rag_tool: Knot | Tool,
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        max_iterations: Knot | int = 3,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            query=query,
            rag_tool=rag_tool,
            llm=llm,
            max_iterations=max_iterations,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        query: str,
        rag_tool: Tool,
        llm: LLMProvider,
        max_iterations: int = 3,
        **_: Any,
    ) -> Any:
        """Drive the RAG tool loop and return the final answer as a source knot.

        Args:
            query: The user question the agent must answer.
            rag_tool: The retrieval tool the agent calls each round.
            llm: The provider deciding whether to ask a follow-up.
            max_iterations: Hard upper bound on tool calls (>= 1).

        Returns:
            A source knot whose output is the final :class:`AgentResponse`.

        Raises:
            TypeError: If ``query``/``rag_tool``/``llm`` are the wrong type.
            ValueError: If ``max_iterations`` is not a positive integer.
        """
        if not isinstance(query, str):
            raise TypeError(
                f"AgenticRagPipeline: query must be a string, got {type(query).__name__}"
            )
        if not isinstance(rag_tool, Tool):
            raise TypeError(
                f"AgenticRagPipeline: rag_tool must be a Tool, got {type(rag_tool).__name__}"
            )
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                f"AgenticRagPipeline: llm must be an LLMProvider, got {type(llm).__name__}"
            )
        if not isinstance(max_iterations, int) or max_iterations <= 0:
            raise ValueError(
                f"AgenticRagPipeline: max_iterations must be a positive int, got {max_iterations!r}"
            )
        current_question = query
        answer = ""
        for iteration in range(max_iterations):
            result = await rag_tool.invoke({"question": current_question})
            answer = self._tool_answer(result)
            if iteration == max_iterations - 1:
                break
            follow_up = await self._next_question(llm, query, answer)
            if follow_up is None:
                break
            current_question = follow_up
        final = AgentResponse(content=answer, finish_reason="stop")

        class _ResultSource(Source):
            async def process(self, **_: Any) -> AgentResponse:
                return final

        return _ResultSource(_config=KnotConfig(id="result"))

    @staticmethod
    async def _next_question(llm: LLMProvider, query: str, answer: str) -> str | None:
        """Ask the LLM for a follow-up question, or ``None`` when the answer suffices."""
        prompt = (
            "You are an agent answering a question with a retrieval tool. Given the "
            "original question and the tool's latest answer, reply with exactly 'DONE' if "
            "the answer fully resolves the question, or 'FOLLOWUP: <a more specific "
            f"question>' otherwise.\n\nOriginal question: {query}\n\nLatest answer: {answer}"
        )
        raw = await llm.chat([{"role": "user", "content": prompt}])
        reply = AgenticRagPipeline._extract_text(raw).strip()
        if reply.upper().startswith("FOLLOWUP:"):
            follow_up = reply.split(":", 1)[1].strip()
            return follow_up or None
        return None

    @staticmethod
    def _tool_answer(result: Any) -> str:
        """Pull the answer string out of a RAG-tool result."""
        if isinstance(result, Mapping):
            answer = result.get("answer")
            if isinstance(answer, str):
                return answer
        return str(result)

    @staticmethod
    def _extract_text(raw: Any) -> str:
        if isinstance(raw, str):
            return raw
        if isinstance(raw, dict):
            content = raw.get("content")
            if isinstance(content, str):
                return content
        return str(raw)
