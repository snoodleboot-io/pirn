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

Algorithm:
    1. Retrieve up to ``_retrieval_top_k`` entity/relation hits from
       ``graph_memory`` via :class:`MemorySearchRetriever`.
    2. Flatten the hits into a typed sub-graph context block with a
       ``hop_count`` breadcrumb via :class:`SubGraphContextBuilder`.
    3. Build a prompt that instructs the LLM to cite entities by id
       via :class:`RAGPromptBuilder`.
    4. Generate an answer with :class:`LLMChatCall`.
    5. Wrap the answer as an :class:`AgentResponse` via
       :class:`RAGResponseBuilder` and return it.

References:
    - Graph RAG (Microsoft): https://arxiv.org/abs/2404.16130
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
from pirn.nodes.sub_tapestry import SubTapestry


class GraphRAGPipeline(SubTapestry):
    """Graph-shaped RAG pipeline returning an :class:`AgentResponse`."""

    _retrieval_top_k: int = 25

    def __init__(
        self,
        *,
        query: Knot | str,
        graph_memory: Knot | MemoryStore,
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        hop_count: Knot | int = 2,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            query=query,
            graph_memory=graph_memory,
            llm=llm,
            hop_count=hop_count,
            _config=_config,
            **kwargs,
        )

    async def process(
        self, query: str, graph_memory: MemoryStore, llm: LLMProvider, hop_count: int, **_: Any
    ) -> Any:
        """Retrieve graph entities, build a sub-graph context, and answer the query via the LLM.

        Args:
            query: The user query string to retrieve graph context for and answer.

        Returns:
            An AgentResponse containing the LLM-generated answer grounded in the sub-graph.

        Raises:
            TypeError: If query is not a string.
        """
        retrieved = MemorySearchRetriever(
            store=graph_memory,
            query=query,
            top_k=self._retrieval_top_k,
            _config=KnotConfig(id="retrieve"),
        )
        sub_graph = SubGraphContextBuilder(
            retrieved=retrieved,
            hop_count=hop_count,
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
            llm=llm,
            _config=KnotConfig(id="generate"),
        )
        return RAGResponseBuilder(
            answer=answer,
            _config=KnotConfig(id="response"),
        )
