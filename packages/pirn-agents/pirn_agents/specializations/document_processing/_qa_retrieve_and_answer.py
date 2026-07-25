"""``_QARetrieveAndAnswer`` — internal helper Knot for :class:`DocumentQAPipeline`.

Embeds the chunks plus the question, ranks chunks by cosine similarity,
and asks the LLM to answer using the top-k chunks as context. Internal
API.

Algorithm:
    1. Validate that ``question`` is a non-empty string.
    2. Return an empty-content response immediately when ``chunks`` is empty.
    3. Call ``embedder.embed([question, *chunks])`` to obtain all vectors
       in a single round-trip.
    4. Separate the question vector from the chunk vectors.
    5. Compute cosine similarity between the question vector and each
       chunk vector.
    6. Sort (descending) and take the top-``top_k`` chunks.
    7. Format the selected chunks as a numbered context block.
    8. Call ``llm.chat`` with a system instruction and the context + question.
    9. Extract and return the text as an :class:`AgentResponse`.

Math:
    Cosine similarity between vectors **a** and **b**::

        sim(a, b) = (a · b) / (||a|| * ||b||)

    where ``·`` is the dot product and ``||·||`` is the L2 norm.
    Returns 0.0 when either vector is the zero vector.

References:
    - Cosine similarity: https://en.wikipedia.org/wiki/Cosine_similarity
"""

from __future__ import annotations

import math
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.embedding_provider import EmbeddingProvider
from pirn_agents.llm_provider import LLMProvider
from pirn_agents.types.agent_response import AgentResponse


class _QARetrieveAndAnswer(Knot):
    """Embed chunks + question, pick top-k by cosine, ask the LLM."""

    def __init__(
        self,
        *,
        chunks: Knot,
        question: Knot | str,
        llm: Knot | LLMProvider,
        embedder: Knot | EmbeddingProvider,
        top_k: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            chunks=chunks,
            question=question,
            llm=llm,
            embedder=embedder,
            top_k=top_k,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        chunks: list[str],
        question: str,
        llm: LLMProvider,
        embedder: EmbeddingProvider,
        top_k: int,
        **_: Any,
    ) -> AgentResponse:
        """Embed chunks and question, select top-k by cosine similarity, and answer via the LLM.

        Args:
            chunks: The list of text chunks to embed and rank.
            question: The user question to answer using the top-k retrieved chunks.
            llm: The LLM provider to use for answering.
            embedder: The embedding provider for semantic retrieval.
            top_k: Number of top chunks to include as context.

        Returns:
            An AgentResponse containing the LLM's answer grounded in the retrieved context.

        Raises:
            TypeError: If question is not a non-empty string.
            RuntimeError: If the embedder returns the wrong number of vectors.
        """
        if not isinstance(question, str) or not question:
            raise TypeError(
                f"DocumentQAPipeline: question must be a non-empty string, got {question!r}"
            )
        if not chunks:
            return AgentResponse(
                content="No content was available in the document.",
                finish_reason="stop",
            )
        embeddings = await embedder.embed([question, *chunks])
        if len(embeddings) != len(chunks) + 1:
            raise RuntimeError("DocumentQAPipeline: embedder returned wrong vector count")
        question_vec = embeddings[0]
        chunk_vecs = embeddings[1:]
        scored = [
            (self._cosine(question_vec, chunk_vec), chunk)
            for chunk_vec, chunk in zip(chunk_vecs, chunks, strict=False)
        ]
        scored.sort(key=lambda pair: pair[0], reverse=True)
        top = [chunk for _, chunk in scored[:top_k]]
        context = "\n\n".join(f"[chunk {i + 1}] {chunk}" for i, chunk in enumerate(top))
        chat_messages = [
            {
                "role": "system",
                "content": (
                    "Answer the user's question using the supplied document "
                    "excerpts. If the excerpts are insufficient, say so."
                ),
            },
            {
                "role": "user",
                "content": (f"Document excerpts:\n{context}\n\nQuestion: {question}"),
            },
        ]
        raw = await llm.chat(chat_messages)
        return AgentResponse(
            content=_QARetrieveAndAnswer._extract_text(raw),
            finish_reason="stop",
        )

    @staticmethod
    def _cosine(vec_a: list[float], vec_b: list[float]) -> float:
        if len(vec_a) != len(vec_b) or not vec_a:
            return 0.0
        dot = sum(elem_a * elem_b for elem_a, elem_b in zip(vec_a, vec_b, strict=False))
        norm_a = math.sqrt(sum(elem_a * elem_a for elem_a in vec_a))
        norm_b = math.sqrt(sum(elem_b * elem_b for elem_b in vec_b))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / (norm_a * norm_b)

    @staticmethod
    def _extract_text(raw: Any) -> str:
        if isinstance(raw, str):
            return raw
        if isinstance(raw, dict):
            content = raw.get("content")
            if isinstance(content, str):
                return content
            if isinstance(content, list) and content:
                first = content[0]
                if isinstance(first, dict):
                    text = first.get("text")
                    if isinstance(text, str):
                        return text
                if isinstance(first, str):
                    return first
            text = raw.get("text")
            if isinstance(text, str):
                return text
        return str(raw)
