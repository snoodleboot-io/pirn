"""``_QARetrieveAndAnswer`` — internal helper Knot for :class:`DocumentQAPipeline`.

Embeds the chunks plus the question, ranks chunks by cosine similarity,
and asks the LLM to answer using the top-k chunks as context. Internal
API.
"""

from __future__ import annotations

import math
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.domains.ml.embedding_provider import EmbeddingProvider


class _QARetrieveAndAnswer(Knot):
    """Embed chunks + question, pick top-k by cosine, ask the LLM."""

    def __init__(
        self,
        *,
        chunks: Knot,
        question: Knot | str,
        llm: LLMProvider,
        embedder: EmbeddingProvider,
        top_k: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        self._llm = llm
        self._embedder = embedder
        self._top_k = top_k
        super().__init__(
            chunks=chunks,
            question=question,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        chunks: list[str],
        question: str,
        **_: Any,
    ) -> AgentResponse:
        if not isinstance(question, str) or not question:
            raise TypeError(
                "DocumentQAPipeline: question must be a non-empty string, "
                f"got {question!r}"
            )
        if not chunks:
            return AgentResponse(
                content="No content was available in the document.",
                finish_reason="stop",
            )
        embeddings = await self._embedder.embed([question, *chunks])
        if len(embeddings) != len(chunks) + 1:
            raise RuntimeError(
                "DocumentQAPipeline: embedder returned wrong vector count"
            )
        question_vec = embeddings[0]
        chunk_vecs = embeddings[1:]
        scored = [
            (self._cosine(question_vec, chunk_vec), chunk)
            for chunk_vec, chunk in zip(chunk_vecs, chunks)
        ]
        scored.sort(key=lambda pair: pair[0], reverse=True)
        top = [chunk for _, chunk in scored[: self._top_k]]
        context = "\n\n".join(
            f"[chunk {i + 1}] {chunk}" for i, chunk in enumerate(top)
        )
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
                "content": (
                    f"Document excerpts:\n{context}\n\nQuestion: {question}"
                ),
            },
        ]
        raw = await self._llm.chat(chat_messages)
        return AgentResponse(
            content=_QARetrieveAndAnswer._extract_text(raw),
            finish_reason="stop",
        )

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        if len(a) != len(b) or not a:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
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
