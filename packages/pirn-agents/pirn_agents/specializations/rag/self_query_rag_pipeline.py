"""``SelfQueryRagPipeline`` — extract a metadata filter, then retrieve + answer.

A :class:`SubTapestry` that wires:

1. :class:`SelfQueryFilterExtractor` — split the query into a semantic query and
   a whitelisted metadata filter.
2. :class:`SelfQueryRetriever` — embed the semantic query and search the vector
   store under that filter (F4 metadata-filter support).
3. :class:`RAGSynthesizer` — synthesize a grounded answer to the original query.

Self-query pushes structured constraints ("author = X", "year >= 2023") into the
vector store's pre-filter instead of hoping the embedding captures them.

References:
    - LangChain SelfQueryRetriever design.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_agents.embedding_provider import EmbeddingProvider
from pirn_agents.llm_provider import LLMProvider
from pirn_agents.specializations.rag.rag_synthesizer import RAGSynthesizer
from pirn_agents.specializations.rag.self_query_filter_extractor import SelfQueryFilterExtractor
from pirn_agents.specializations.rag.self_query_retriever import SelfQueryRetriever
from pirn_agents.vector_stores.vector_memory_store import VectorMemoryStore


class SelfQueryRagPipeline(SubTapestry):
    """Extract a metadata filter, retrieve under it, then synthesize an answer."""

    def __init__(
        self,
        *,
        query: Knot | str,
        store: Knot | VectorMemoryStore,
        embedder: Knot | EmbeddingProvider,
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        filterable_fields: Knot | list[str] | None = None,
        top_k: Knot | int = 5,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            query=query,
            store=store,
            embedder=embedder,
            llm=llm,
            filterable_fields=filterable_fields,
            top_k=top_k,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        query: str,
        store: VectorMemoryStore,
        embedder: EmbeddingProvider,
        llm: LLMProvider,
        filterable_fields: list[str] | None = None,
        top_k: int = 5,
        **_: Any,
    ) -> Any:
        """Wire filter extraction → filtered retrieval → synthesis.

        Args:
            query: The natural-language query to split, retrieve for, and answer.
            store: The vector store queried under the extracted filter.
            embedder: The provider used to embed the semantic query.
            llm: The provider used for extraction and synthesis.
            filterable_fields: Metadata fields the filter may use; empty when None.
            top_k: Number of hits fed to synthesis.

        Returns:
            The :class:`RAGSynthesizer` sink knot whose output is the answer.

        Raises:
            TypeError: If ``query``/``store``/``embedder``/``llm`` are the wrong type.
        """
        if not isinstance(query, str):
            raise TypeError(
                f"SelfQueryRagPipeline: query must be a string, got {type(query).__name__}"
            )
        if not isinstance(store, VectorMemoryStore):
            raise TypeError(
                f"SelfQueryRagPipeline: store must be a VectorMemoryStore, "
                f"got {type(store).__name__}"
            )
        if not isinstance(embedder, EmbeddingProvider):
            raise TypeError(
                f"SelfQueryRagPipeline: embedder must be an EmbeddingProvider, "
                f"got {type(embedder).__name__}"
            )
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                f"SelfQueryRagPipeline: llm must be an LLMProvider, got {type(llm).__name__}"
            )
        spec = SelfQueryFilterExtractor(
            query=query,
            llm=llm,
            filterable_fields=filterable_fields if filterable_fields is not None else [],
            _config=KnotConfig(id="extract"),
        )
        documents = SelfQueryRetriever(
            query_spec=spec,
            store=store,
            embedder=embedder,
            top_k=top_k,
            _config=KnotConfig(id="retrieve"),
        )
        return RAGSynthesizer(
            query=query,
            documents=documents,
            llm=llm,
            _config=KnotConfig(id="synthesize"),
        )
