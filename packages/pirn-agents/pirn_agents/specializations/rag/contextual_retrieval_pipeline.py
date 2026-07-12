"""``ContextualRetrievalPipeline`` — retrieve → rerank → compress → synthesize.

A :class:`SubTapestry` that wires the post-retrieval stack:

1. :class:`MemorySearchRetriever` — over-fetch candidate documents.
2. :class:`Reranker` — reorder candidates by relevance under a top-k budget,
   using an injected F4 :class:`RerankerBackend` when supplied, else the LLM.
3. :class:`ContextualCompressor` — trim each survivor to its query-relevant span.
4. :class:`RAGSynthesizer` — synthesize a grounded answer over the compressed set.

Over-fetching then reranking and compressing beats naive top-k: the retriever's
recall is high but noisy, and the rerank + compress passes concentrate the signal
before synthesis.

References:
    - Nogueira & Cho, "Passage Re-ranking with BERT" (2019):
      https://arxiv.org/abs/1901.04085
    - Anthropic, "Contextual Retrieval" (2024).
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.providers.llm_provider import LLMProvider
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_agents.memory_store import MemoryStore
from pirn_agents.specializations.rag.contextual_compressor import ContextualCompressor
from pirn_agents.specializations.rag.memory_search_retriever import MemorySearchRetriever
from pirn_agents.specializations.rag.rag_synthesizer import RAGSynthesizer
from pirn_agents.specializations.rag.reranker import Reranker


class ContextualRetrievalPipeline(SubTapestry):
    """Over-fetch, rerank under a budget, compress, then synthesize."""

    def __init__(
        self,
        *,
        query: Knot | str,
        memory: Knot | MemoryStore,
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        reranker: Knot | Any | None = None,
        fetch_k: Knot | int = 10,
        rerank_k: Knot | int = 5,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            query=query,
            memory=memory,
            llm=llm,
            reranker=reranker,
            fetch_k=fetch_k,
            rerank_k=rerank_k,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        query: str,
        memory: MemoryStore,
        llm: LLMProvider,
        reranker: Any = None,
        fetch_k: int = 10,
        rerank_k: int = 5,
        **_: Any,
    ) -> Any:
        """Wire retrieval → rerank → compression → synthesis.

        Args:
            query: The user query to retrieve for and answer.
            memory: The memory store over-fetched for candidates.
            llm: The provider used for reranking (fallback), compression, synthesis.
            reranker: Optional F4 rerank backend; the LLM reranks when None.
            fetch_k: Number of candidates over-fetched before reranking.
            rerank_k: Top-k budget kept after reranking.

        Returns:
            The :class:`RAGSynthesizer` sink knot whose output is the answer.

        Raises:
            TypeError: If ``query``/``memory``/``llm`` are the wrong type.
            ValueError: If ``fetch_k``/``rerank_k`` are not positive ints.
        """
        if not isinstance(query, str):
            raise TypeError(
                f"ContextualRetrievalPipeline: query must be a string, got {type(query).__name__}"
            )
        if not isinstance(memory, MemoryStore):
            raise TypeError(
                "ContextualRetrievalPipeline: memory must be a MemoryStore, "
                f"got {type(memory).__name__}"
            )
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                f"ContextualRetrievalPipeline: llm must be an LLMProvider, got {type(llm).__name__}"
            )
        if not isinstance(fetch_k, int) or fetch_k <= 0:
            raise ValueError(
                f"ContextualRetrievalPipeline: fetch_k must be a positive int, got {fetch_k!r}"
            )
        if not isinstance(rerank_k, int) or rerank_k <= 0:
            raise ValueError(
                f"ContextualRetrievalPipeline: rerank_k must be a positive int, got {rerank_k!r}"
            )
        retrieved = MemorySearchRetriever(
            store=memory,
            query=query,
            top_k=fetch_k,
            _config=KnotConfig(id="retrieve"),
        )
        reranked = Reranker(
            query=query,
            documents=retrieved,
            llm=llm if reranker is None else None,
            reranker=reranker,
            top_k=rerank_k,
            _config=KnotConfig(id="rerank"),
        )
        compressed = ContextualCompressor(
            query=query,
            documents=reranked,
            llm=llm,
            _config=KnotConfig(id="compress"),
        )
        return RAGSynthesizer(
            query=query,
            documents=compressed,
            llm=llm,
            _config=KnotConfig(id="synthesize"),
        )
