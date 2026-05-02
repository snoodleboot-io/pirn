"""``GraphRAGPipeline`` — graph-aware retrieval-augmented generation.

The graph variant assumes the user supplies a graph-shaped
:class:`MemoryStore` whose :meth:`MemoryStore.search` returns entity
and relation mappings. Stages composed inside the inner
:class:`Tapestry`:

1. :class:`MemorySearchRetriever` — fetch entity/relation hits.
2. :class:`SubGraphContextBuilder` — flatten them into a typed
   sub-graph block, retaining a hop-count breadcrumb for the prompt.
3. :class:`RAGPromptBuilder` — fold the sub-graph block plus the query
   into a prompt string.
4. :class:`LLMChatCall` — generate the answer over the sub-graph.
5. :class:`RAGResponseBuilder` — wrap as :class:`AgentResponse`.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider
from pirn.domains.agents.memory_store import MemoryStore
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
from pirn.domains.agents.specializations.rag.sub_graph_context_builder import (
    SubGraphContextBuilder,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class GraphRAGPipeline(SubTapestry):
    """Graph-shaped RAG pipeline returning an :class:`AgentResponse`."""

    _retrieval_top_k: int = 25

    def __init__(
        self,
        *,
        query: Knot | str,
        graph_memory: MemoryStore,
        llm: LLMProvider,
        _config: KnotConfig,
        hop_count: int = 2,
        **kwargs: Any,
    ) -> None:
        if not isinstance(graph_memory, MemoryStore):
            raise TypeError(
                "GraphRAGPipeline: graph_memory must be a MemoryStore, "
                f"got {type(graph_memory).__name__}"
            )
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                "GraphRAGPipeline: llm must be an LLMProvider, "
                f"got {type(llm).__name__}"
            )
        if not isinstance(hop_count, int) or hop_count <= 0:
            raise ValueError(
                "GraphRAGPipeline: hop_count must be a positive int, "
                f"got {hop_count!r}"
            )
        self._graph_memory = graph_memory
        self._llm = llm
        self._hop_count = hop_count
        super().__init__(query=query, _config=_config, **kwargs)

    async def process(self, query: str, **_: Any) -> AgentResponse:
        if not isinstance(query, str):
            raise TypeError(
                "GraphRAGPipeline: query must be a string, "
                f"got {type(query).__name__}"
            )
        with Tapestry() as inner:
            retrieved = MemorySearchRetriever(
                store=self._graph_memory,
                query=query,
                top_k=self._retrieval_top_k,
                _config=KnotConfig(id="retrieve"),
            )
            sub_graph = SubGraphContextBuilder(
                retrieved=retrieved,
                hop_count=self._hop_count,
                _config=KnotConfig(id="sub_graph"),
            )
            prompt = RAGPromptBuilder(
                query=query,
                retrieved=sub_graph,
                instruction=(
                    "Answer the question using the retrieved sub-graph "
                    "context. Cite entities by id when relevant."
                ),
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
