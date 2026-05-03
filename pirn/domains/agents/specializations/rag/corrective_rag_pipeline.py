"""``CorrectiveRAGPipeline`` — RAG with relevance scoring + tool fallback.

Stages composed inside the inner :class:`Tapestry`:

1. :class:`MemorySearchRetriever` — fetch top-k memories.
2. :class:`RelevanceGate` — keep only entries above ``relevance_threshold``.
3. :class:`CorrectiveRouter` — when nothing survives the gate, invoke
   ``fallback_tool`` (a caller-injected :class:`Tool`, typically a web
   search) and return its output as a single synthetic document.
4. :class:`RAGPromptBuilder` — fold the resulting docs and the query
   into a prompt.
5. :class:`LLMChatCall` — generate the answer.
6. :class:`RAGResponseBuilder` — wrap as :class:`AgentResponse`.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider
from pirn.domains.agents.memory_store import MemoryStore
from pirn.domains.agents.specializations.rag.corrective_router import (
    CorrectiveRouter,
)
from pirn.domains.agents.specializations.rag.llm_chat_call import LLMChatCall
from pirn.domains.agents.specializations.rag.memory_search_retriever import (
    MemorySearchRetriever,
)
from pirn.domains.agents.specializations.rag.rag_prompt_builder import (
    RAGPromptBuilder,
)
from pirn.domains.agents.specializations.rag.rag_response_builder import (
    RAGResponseBuilder,
)
from pirn.domains.agents.specializations.rag.relevance_gate import (
    RelevanceGate,
)
from pirn.domains.agents.tool import Tool
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class CorrectiveRAGPipeline(SubTapestry):
    """RAG variant that falls back to a web-search tool on weak retrieval."""

    def __init__(
        self,
        *,
        query: Knot | str,
        memory: MemoryStore,
        llm: LLMProvider,
        fallback_tool: Tool,
        _config: KnotConfig,
        top_k: int = 5,
        relevance_threshold: float = 0.5,
        **kwargs: Any,
    ) -> None:
        if not isinstance(memory, MemoryStore):
            raise TypeError(
                "CorrectiveRAGPipeline: memory must be a MemoryStore, "
                f"got {type(memory).__name__}"
            )
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                "CorrectiveRAGPipeline: llm must be an LLMProvider, "
                f"got {type(llm).__name__}"
            )
        if not isinstance(fallback_tool, Tool):
            raise TypeError(
                "CorrectiveRAGPipeline: fallback_tool must be a Tool, "
                f"got {type(fallback_tool).__name__}"
            )
        if not isinstance(top_k, int) or top_k <= 0:
            raise ValueError(
                "CorrectiveRAGPipeline: top_k must be a positive int, "
                f"got {top_k!r}"
            )
        if not isinstance(relevance_threshold, (int, float)):
            raise TypeError(
                "CorrectiveRAGPipeline: relevance_threshold must be a number, "
                f"got {type(relevance_threshold).__name__}"
            )
        if not 0.0 <= float(relevance_threshold) <= 1.0:
            raise ValueError(
                "CorrectiveRAGPipeline: relevance_threshold must be in "
                f"[0.0, 1.0], got {relevance_threshold!r}"
            )
        self._memory = memory
        self._llm = llm
        self._fallback_tool = fallback_tool
        self._top_k = top_k
        self._relevance_threshold = float(relevance_threshold)
        super().__init__(query=query, _config=_config, **kwargs)

    async def process(self, query: str, **_: Any) -> AgentResponse:
        """Retrieve, score, correct via fallback if needed, and answer the query using the LLM.

        Args:
            query: The user query string to retrieve context for and answer.

        Returns:
            An AgentResponse containing the LLM-generated answer.

        Raises:
            TypeError: If query is not a string.
        """
        if not isinstance(query, str):
            raise TypeError(
                "CorrectiveRAGPipeline: query must be a string, "
                f"got {type(query).__name__}"
            )
        with Tapestry() as inner:
            retrieved = MemorySearchRetriever(
                store=self._memory,
                query=query,
                top_k=self._top_k,
                _config=KnotConfig(id="retrieve"),
            )
            relevant = RelevanceGate(
                query=query,
                retrieved=retrieved,
                threshold=self._relevance_threshold,
                _config=KnotConfig(id="score"),
            )
            routed = CorrectiveRouter(
                query=query,
                relevant_docs=relevant,
                fallback_tool=self._fallback_tool,
                _config=KnotConfig(id="route"),
            )
            prompt = RAGPromptBuilder(
                query=query,
                retrieved=routed,
                _config=KnotConfig(id="prompt"),
            )
            answer = LLMChatCall(
                prompt=prompt,
                llm=self._llm,
                _config=KnotConfig(id="generate"),
            )
            RAGResponseBuilder(
                answer=answer,
                _config=KnotConfig(id="response"),
            )
        inner_result = await self._run_inner(inner)
        response = inner_result.outputs.get("response")
        if not isinstance(response, AgentResponse):
            return AgentResponse(content="", finish_reason="length")
        return response
