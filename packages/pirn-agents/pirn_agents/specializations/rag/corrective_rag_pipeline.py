"""``CorrectiveRAGPipeline`` — RAG with relevance scoring + tool fallback.

Stages composed inside the inner :class:`Tapestry`:

1. :class:`MemorySearchRetriever` — fetch top-k memories.
2. :class:`RelevanceCheck` — keep only entries above ``relevance_threshold``.
3. :class:`CorrectiveRouter` — when nothing survives the gate, invoke
   ``fallback_tool`` (a caller-injected :class:`Tool`, typically a web
   search) and return its output as a single synthetic document.
4. :class:`RAGPromptBuilder` — fold the resulting docs and the query
   into a prompt.
5. :class:`LLMChatCall` — generate the answer.
6. :class:`RAGResponseBuilder` — wrap as :class:`AgentResponse`.

Algorithm:
    1. Retrieve ``top_k`` hits from memory via :class:`MemorySearchRetriever`.
    2. Filter hits to those above ``relevance_threshold`` via
       :class:`RelevanceCheck`.
    3. If the filtered set is empty, invoke ``fallback_tool`` with the query
       via :class:`CorrectiveRouter`; otherwise pass the filtered docs
       through unchanged.
    4. Build a prompt from the resulting docs and the original query via
       :class:`RAGPromptBuilder`.
    5. Generate an answer with :class:`LLMChatCall`.
    6. Wrap the answer as an :class:`AgentResponse` via
       :class:`RAGResponseBuilder` and return it.

References:
    - Corrective RAG: https://arxiv.org/abs/2401.15884
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_agents.llm_provider import LLMProvider
from pirn_agents.memory_store import MemoryStore
from pirn_agents.specializations.rag.corrective_router import (
    CorrectiveRouter,
)
from pirn_agents.specializations.rag.llm_chat_call import LLMChatCall
from pirn_agents.specializations.rag.memory_search_retriever import (
    MemorySearchRetriever,
)
from pirn_agents.specializations.rag.rag_prompt_builder import (
    RAGPromptBuilder,
)
from pirn_agents.specializations.rag.rag_response_builder import (
    RAGResponseBuilder,
)
from pirn_agents.specializations.rag.relevance_gate import (
    RelevanceCheck,
)
from pirn_agents.tool import Tool


class CorrectiveRAGPipeline(SubTapestry):
    """RAG variant that falls back to a web-search tool on weak retrieval."""

    def __init__(
        self,
        *,
        query: Knot | str,
        memory: Knot | MemoryStore,
        llm: Knot | LLMProvider,
        fallback_tool: Knot | Tool,
        _config: KnotConfig,
        top_k: Knot | int = 5,
        relevance_threshold: Knot | float = 0.5,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            query=query,
            memory=memory,
            llm=llm,
            fallback_tool=fallback_tool,
            top_k=top_k,
            relevance_threshold=relevance_threshold,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        query: str,
        memory: MemoryStore,
        llm: LLMProvider,
        fallback_tool: Tool,
        top_k: int,
        relevance_threshold: float,
        **_: Any,
    ) -> Any:
        """Retrieve, score, correct via fallback if needed, and answer the query using the LLM.

        Args:
            query: The user query string to retrieve context for and answer.

        Returns:
            An AgentResponse containing the LLM-generated answer.

        Raises:
            TypeError: If query is not a string.
        """
        retrieved = MemorySearchRetriever(
            store=memory,
            query=query,
            top_k=top_k,
            _config=KnotConfig(id="retrieve"),
        )
        relevant = RelevanceCheck(
            query=query,
            retrieved=retrieved,
            threshold=relevance_threshold,
            _config=KnotConfig(id="score"),
        )
        routed = CorrectiveRouter(
            query=query,
            relevant_docs=relevant,
            fallback_tool=fallback_tool,
            _config=KnotConfig(id="route"),
        )
        prompt = RAGPromptBuilder(
            query=query,
            retrieved=routed,
            _config=KnotConfig(id="prompt"),
        )
        answer = LLMChatCall(
            prompt=prompt,
            llm=llm,
            _config=KnotConfig(id="generate"),
        )
        return RAGResponseBuilder(
            answer=answer,
            _config=KnotConfig(id="response"),
        )
