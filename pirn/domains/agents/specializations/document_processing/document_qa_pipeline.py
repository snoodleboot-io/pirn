"""``DocumentQAPipeline`` — Q&A over a single document.

A :class:`SubTapestry` that loads a document, splits it into chunks,
embeds each chunk plus the question, ranks chunks by cosine similarity,
and asks the LLM to answer using the top-k chunks as context.

The pipeline does not depend on a global :class:`MemoryStore` — the
question is scoped to the supplied source, so the embeddings are kept
in-process for the lifetime of one request and discarded once the
answer is produced.

Algorithm:
    1. ``_QALoadAndChunk`` loads the document from a file path or HTTP/HTTPS URL and
       splits it into overlapping character windows.
    2. Each chunk is embedded via the ``EmbeddingProvider``; the question is embedded
       using the same provider.
    3. Cosine similarity is computed between the question vector and every chunk
       vector; the top-k chunks are selected.
    4. ``_QARetrieveAndAnswer`` injects the top-k chunks as context into the LLM
       prompt and returns the model response as an :class:`AgentResponse`.

Math:
    Cosine similarity: ``sim(q, c) = (q · c) / (||q|| * ||c||)`` where ``q`` is the
    query embedding and ``c`` is a chunk embedding. Top-k selection by descending
    similarity score.

References:
    - Lewis et al., 2020 — RAG: Retrieval-Augmented Generation for
      Knowledge-Intensive NLP Tasks (arXiv 2005.11401).
    - Karpukhin et al., 2020 — Dense Passage Retrieval for Open-Domain QA
      (arXiv 2004.04906).
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider
from pirn.domains.agents.specializations.document_processing._qa_load_and_chunk import (
    _QALoadAndChunk,
)
from pirn.domains.agents.specializations.document_processing._qa_retrieve_and_answer import (
    _QARetrieveAndAnswer,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.domains.ml.embedding_provider import EmbeddingProvider
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class DocumentQAPipeline(SubTapestry):
    """Question-answer over a single document; returns :class:`AgentResponse`."""

    _default_chunk_size: int = 1000

    def __init__(
        self,
        *,
        source: Knot | str,
        question: Knot | str,
        llm: Knot | LLMProvider,
        embedder: Knot | EmbeddingProvider,
        _config: KnotConfig,
        top_k: Knot | int = 3,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            source=source,
            question=question,
            llm=llm,
            embedder=embedder,
            top_k=top_k,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        source: str,
        question: str,
        llm: LLMProvider,
        embedder: EmbeddingProvider,
        top_k: int = 3,
        **_: Any,
    ) -> AgentResponse:
        """Retrieve the top-k relevant chunks from source and answer the question via the LLM.

        Args:
            source: A local file path or http(s):// URL identifying the document to search.
            question: The natural-language question to answer from the document.
            llm: The LLM provider to use for answering.
            embedder: The embedding provider for semantic retrieval.
            top_k: Number of top chunks to include as context.

        Returns:
            An AgentResponse containing the LLM's answer grounded in the retrieved chunks.

        Raises:
            TypeError: If source or question is not a non-empty string.
            ValueError: If top_k is not a positive int.
        """
        if not isinstance(top_k, int) or top_k <= 0:
            raise ValueError(f"DocumentQAPipeline: top_k must be a positive int, got {top_k!r}")
        if not isinstance(source, str) or not source:
            raise TypeError(
                f"DocumentQAPipeline: source must be a non-empty string, got {source!r}"
            )
        if not isinstance(question, str) or not question:
            raise TypeError(
                f"DocumentQAPipeline: question must be a non-empty string, got {question!r}"
            )
        with Tapestry() as inner:
            chunks = _QALoadAndChunk(
                source=source,
                chunk_size=self._default_chunk_size,
                _config=KnotConfig(id="chunk"),
            )
            _QARetrieveAndAnswer(
                chunks=chunks,
                question=question,
                llm=llm,
                embedder=embedder,
                top_k=top_k,
                _config=KnotConfig(id="answer"),
            )
        inner_result = await self._run_inner(inner)
        response = inner_result.outputs.get("answer")
        if not isinstance(response, AgentResponse):
            return AgentResponse(content="", finish_reason="length")
        return response
