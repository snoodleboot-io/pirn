"""``DocumentQAPipeline`` — Q&A over a single document.

A :class:`SubTapestry` that loads a document, splits it into chunks,
embeds each chunk plus the question, ranks chunks by cosine similarity,
and asks the LLM to answer using the top-k chunks as context.

The pipeline does not depend on a global :class:`MemoryStore` — the
question is scoped to the supplied source, so the embeddings are kept
in-process for the lifetime of one request and discarded once the
answer is produced.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider
from pirn.domains.agents.specializations.document_processing._qa_load_and_chunk import (  # noqa: E501
    _QALoadAndChunk,
)
from pirn.domains.agents.specializations.document_processing._qa_retrieve_and_answer import (  # noqa: E501
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
        llm: LLMProvider,
        embedder: EmbeddingProvider,
        _config: KnotConfig,
        top_k: int = 3,
        **kwargs: Any,
    ) -> None:
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                "DocumentQAPipeline: llm must be an LLMProvider, "
                f"got {type(llm).__name__}"
            )
        if not isinstance(embedder, EmbeddingProvider):
            raise TypeError(
                "DocumentQAPipeline: embedder must be an EmbeddingProvider, "
                f"got {type(embedder).__name__}"
            )
        if not isinstance(top_k, int) or top_k <= 0:
            raise ValueError(
                "DocumentQAPipeline: top_k must be a positive int, "
                f"got {top_k!r}"
            )
        self._llm = llm
        self._embedder = embedder
        self._top_k = top_k
        super().__init__(
            source=source,
            question=question,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        source: str,
        question: str,
        **_: Any,
    ) -> AgentResponse:
        """Retrieve the top-k relevant chunks from source and answer the question via the LLM.

        Args:
            source: A local file path or http(s):// URL identifying the document to search.
            question: The natural-language question to answer from the document.

        Returns:
            An AgentResponse containing the LLM's answer grounded in the retrieved chunks.

        Raises:
            TypeError: If source or question is not a non-empty string.
        """
        if not isinstance(source, str) or not source:
            raise TypeError(
                "DocumentQAPipeline: source must be a non-empty string, "
                f"got {source!r}"
            )
        if not isinstance(question, str) or not question:
            raise TypeError(
                "DocumentQAPipeline: question must be a non-empty string, "
                f"got {question!r}"
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
                llm=self._llm,
                embedder=self._embedder,
                top_k=self._top_k,
                _config=KnotConfig(id="answer"),
            )
        inner_result = await self._run_inner(inner)
        response = inner_result.outputs.get("answer")
        if not isinstance(response, AgentResponse):
            return AgentResponse(content="", finish_reason="length")
        return response
