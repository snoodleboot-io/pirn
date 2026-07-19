"""``RagFusionPipeline`` — RAG-Fusion: multi-query expansion + RRF + synthesize.

A :class:`SubTapestry` that wires:

1. :class:`MultiQueryExpander` — expand the query into N reformulations.
2. :class:`FusionRetriever` — search every reformulation concurrently and fuse
   the rankings with Reciprocal Rank Fusion.
3. :class:`RAGSynthesizer` — generate a grounded, source-citing answer over the
   fused document set.

The multi-query fan-out beats naive single-query retrieval because relevant
documents that only match a paraphrase still surface, and RRF rewards documents
ranked highly by several reformulations.

References:
    - Rackauckas, "RAG-Fusion" (2024): https://arxiv.org/abs/2402.03367
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_agents.llm_provider import LLMProvider
from pirn_agents.memory_store import MemoryStore
from pirn_agents.specializations.rag.fusion_retriever import FusionRetriever
from pirn_agents.specializations.rag.multi_query_expander import MultiQueryExpander
from pirn_agents.specializations.rag.rag_synthesizer import RAGSynthesizer


class RagFusionPipeline(SubTapestry):
    """Expand the query, fuse concurrent retrievals with RRF, then synthesize."""

    def __init__(
        self,
        *,
        query: Knot | str,
        memory: Knot | MemoryStore,
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        num_queries: Knot | int = 4,
        top_k: Knot | int = 5,
        max_concurrency: Knot | int = 4,
        rrf_k: Knot | int = 60,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            query=query,
            memory=memory,
            llm=llm,
            num_queries=num_queries,
            top_k=top_k,
            max_concurrency=max_concurrency,
            rrf_k=rrf_k,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        query: str,
        memory: MemoryStore,
        llm: LLMProvider,
        num_queries: int = 4,
        top_k: int = 5,
        max_concurrency: int = 4,
        rrf_k: int = 60,
        **_: Any,
    ) -> Any:
        """Wire expansion → fusion retrieval → synthesis and return the sink knot.

        Args:
            query: The user query to expand, retrieve for, and answer.
            memory: The memory store searched once per query variant.
            llm: The provider used for expansion and synthesis.
            num_queries: Number of query variants to fan out.
            top_k: Number of fused documents fed to synthesis.
            max_concurrency: Maximum concurrent variant searches.
            rrf_k: The RRF damping constant.

        Returns:
            The :class:`RAGSynthesizer` sink knot whose output is the answer.

        Raises:
            TypeError: If ``query`` is not a string, ``memory`` not a MemoryStore,
                or ``llm`` not an LLMProvider.
        """
        if not isinstance(query, str):
            raise TypeError(
                f"RagFusionPipeline: query must be a string, got {type(query).__name__}"
            )
        if not isinstance(memory, MemoryStore):
            raise TypeError(
                f"RagFusionPipeline: memory must be a MemoryStore, got {type(memory).__name__}"
            )
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                f"RagFusionPipeline: llm must be an LLMProvider, got {type(llm).__name__}"
            )
        variants = MultiQueryExpander(
            query=query,
            llm=llm,
            num_queries=num_queries,
            _config=KnotConfig(id="expand"),
        )
        fused = FusionRetriever(
            queries=variants,
            store=memory,
            top_k=top_k,
            max_concurrency=max_concurrency,
            rrf_k=rrf_k,
            _config=KnotConfig(id="fuse"),
        )
        return RAGSynthesizer(
            query=query,
            documents=fused,
            llm=llm,
            _config=KnotConfig(id="synthesize"),
        )
