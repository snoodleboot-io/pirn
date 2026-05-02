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

import math
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.domains.ml.embedding_provider import EmbeddingProvider
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class _QALoadAndChunk(Knot):
    """Read the source text and return fixed-size chunks (default ~1000 chars)."""

    def __init__(
        self,
        *,
        source: Knot | str,
        chunk_size: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            source=source,
            chunk_size=chunk_size,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        source: str,
        chunk_size: int,
        **_: Any,
    ) -> list[str]:
        text = await _load_text(source)
        if not text:
            return []
        return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]


async def _load_text(source: str) -> str:
    parsed = urlparse(source)
    if parsed.scheme in ("http", "https"):
        try:
            import httpx
        except ImportError as exc:
            raise ImportError(
                "DocumentQAPipeline: http(s) sources require httpx; "
                "install via `pip install pirn[http]`"
            ) from exc
        async with httpx.AsyncClient() as client:
            response = await client.get(source)
            response.raise_for_status()
            return response.text
    return Path(source).read_text(encoding="utf-8")


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
        return AgentResponse(content=_extract_text(raw), finish_reason="stop")

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
