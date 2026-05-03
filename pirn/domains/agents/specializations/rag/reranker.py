"""``Reranker`` — LLM-based relevance re-ranking of retrieved documents.

Takes a list of retrieved documents and a query, calls the LLM to score
the relevance of each document, and returns the top-K reranked documents.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider


class Reranker(Knot):
    """Score retrieved documents by relevance and return top-K reranked."""

    def __init__(
        self,
        *,
        query: Knot | str,
        documents: Knot | list[Mapping[str, Any]],
        llm: LLMProvider,
        _config: KnotConfig,
        top_k: int = 5,
        **kwargs: Any,
    ) -> None:
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                "Reranker: llm must be an LLMProvider, "
                f"got {type(llm).__name__}"
            )
        if not isinstance(top_k, int) or top_k <= 0:
            raise ValueError(
                "Reranker: top_k must be a positive int, "
                f"got {top_k!r}"
            )
        self._llm = llm
        self._top_k = top_k
        super().__init__(
            query=query,
            documents=documents,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        query: str,
        documents: list[Mapping[str, Any]],
        **_: Any,
    ) -> list[Mapping[str, Any]]:
        """Score each document for relevance to the query and return the top-K documents.

        Args:
            query: The query string used as the relevance reference.
            documents: The list of retrieved document Mappings to score.

        Returns:
            A list of up to top_k documents reranked by LLM-assessed relevance.

        Raises:
            TypeError: If query is not a string.
        """
        if not isinstance(query, str):
            raise TypeError(
                "Reranker: query must be a string, "
                f"got {type(query).__name__}"
            )
        if not documents:
            return []

        scored: list[tuple[float, Mapping[str, Any]]] = []
        for doc in documents:
            text = self._doc_text(doc)
            score_prompt = (
                "Score the relevance of the following document to the query "
                "on a scale from 0.0 (not relevant) to 1.0 (highly relevant). "
                "Reply with only the numeric score.\n\n"
                f"Query: {query}\n\nDocument: {text}"
            )
            raw = await self._llm.chat([{"role": "user", "content": score_prompt}])
            score_text = self._extract_text(raw).strip()
            try:
                score = float(score_text)
            except ValueError:
                score = 0.0
            scored.append((score, doc))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [doc for _, doc in scored[: self._top_k]]

    @staticmethod
    def _doc_text(doc: Mapping[str, Any]) -> str:
        parts: list[str] = []
        for value in doc.values():
            if isinstance(value, str):
                parts.append(value)
            else:
                parts.append(str(value))
        return " ".join(parts)

    @staticmethod
    def _extract_text(raw: Any) -> str:
        if isinstance(raw, str):
            return raw
        if isinstance(raw, dict):
            content = raw.get("content")
            if isinstance(content, str):
                return content
        return str(raw)
