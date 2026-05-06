"""``Reranker`` — LLM-based relevance re-ranking of retrieved documents.

Takes a list of retrieved documents and a query, calls the LLM to score
the relevance of each document, and returns the top-K reranked documents.

Algorithm:
    1. Receive ``query`` string, ``documents`` list of Mappings, ``llm``
       provider, and ``top_k`` integer.
    2. Validate inputs: ``query`` must be a string, ``llm`` an
       :class:`LLMProvider`, ``top_k`` a positive integer.
    3. If ``documents`` is empty, return ``[]`` immediately.
    4. For each document, extract its text representation and ask the LLM
       to score its relevance to ``query`` on a 0.0-1.0 scale.
    5. Parse the LLM response as a float; default to 0.0 on parse error.
    6. Sort documents descending by score and return the top ``top_k``.

Math:
    LLM-assigned relevance score :math:`s_i \\in [0.0, 1.0]` for document
    :math:`d_i`. Final ranking selects:

    .. math::

        \\text{top-}k = \\underset{i}{\\text{argtop-}k}\\; s_i

References:
    - Nogueira & Cho, "Passage Re-ranking with BERT" (2019):
      https://arxiv.org/abs/1901.04085
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
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        top_k: Knot | int = 5,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            query=query,
            documents=documents,
            llm=llm,
            top_k=top_k,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        query: str,
        documents: list[Mapping[str, Any]],
        llm: LLMProvider,
        top_k: int = 5,
        **_: Any,
    ) -> list[Mapping[str, Any]]:
        """Score each document for relevance to the query and return the top-K documents.

        Args:
            query: The query string used as the relevance reference.
            documents: The list of retrieved document Mappings to score.
            llm: The LLMProvider used to score each document.
            top_k: The maximum number of documents to return.

        Returns:
            A list of up to top_k documents reranked by LLM-assessed relevance.

        Raises:
            TypeError: If query is not a string or llm is not an LLMProvider.
            ValueError: If top_k is not a positive integer.
        """
        if not isinstance(query, str):
            raise TypeError(f"Reranker: query must be a string, got {type(query).__name__}")
        if not isinstance(llm, LLMProvider):
            raise TypeError(f"Reranker: llm must be an LLMProvider, got {type(llm).__name__}")
        if not isinstance(top_k, int) or top_k <= 0:
            raise ValueError(f"Reranker: top_k must be a positive int, got {top_k!r}")
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
            raw = await llm.chat([{"role": "user", "content": score_prompt}])
            score_text = self._extract_text(raw).strip()
            try:
                score = float(score_text)
            except ValueError:
                score = 0.0
            scored.append((score, doc))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [doc for _, doc in scored[:top_k]]

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
