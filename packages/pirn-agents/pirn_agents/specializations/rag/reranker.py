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

from pirn_agents.llm_provider import LLMProvider
from pirn_agents.rerank.reranker_backend import RerankerBackend


class Reranker(Knot):
    """Score retrieved documents by relevance and return top-K reranked.

    Two interchangeable scoring backings are supported: the default LLM path
    (score each document with an :class:`LLMProvider`) and a provider-neutral
    :class:`~pirn_agents.rerank.reranker_backend.RerankerBackend` (e.g. the
    cross-encoder adapter) injected via ``reranker``. Exactly one of ``llm`` or
    ``reranker`` must be supplied.
    """

    def __init__(
        self,
        *,
        query: Knot | str,
        documents: Knot | list[Mapping[str, Any]],
        _config: KnotConfig,
        llm: Knot | LLMProvider | None = None,
        reranker: Knot | RerankerBackend | None = None,
        top_k: Knot | int = 5,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            query=query,
            documents=documents,
            llm=llm,
            reranker=reranker,
            top_k=top_k,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        query: str,
        documents: list[Mapping[str, Any]],
        llm: LLMProvider | None = None,
        reranker: RerankerBackend | None = None,
        top_k: int = 5,
        **_: Any,
    ) -> list[Mapping[str, Any]]:
        """Score each document for relevance to the query and return the top-K documents.

        Args:
            query: The query string used as the relevance reference.
            documents: The list of retrieved document Mappings to score.
            llm: The LLMProvider used to score each document (LLM path).
            reranker: A provider-neutral scoring backend used instead of the
                LLM when supplied.
            top_k: The maximum number of documents to return.

        Returns:
            A list of up to top_k documents reranked by the chosen backend.

        Raises:
            TypeError: If query is not a string, llm is not an LLMProvider, or
                reranker is not a RerankerBackend.
            ValueError: If top_k is not a positive integer, or neither llm nor
                reranker is provided.
        """
        if not isinstance(query, str):
            raise TypeError(f"Reranker: query must be a string, got {type(query).__name__}")
        if reranker is not None and not isinstance(reranker, RerankerBackend):
            raise TypeError(
                f"Reranker: reranker must be a RerankerBackend, got {type(reranker).__name__}"
            )
        if reranker is None:
            if llm is None:
                raise ValueError("Reranker: either llm or reranker must be provided")
            if not isinstance(llm, LLMProvider):
                raise TypeError(f"Reranker: llm must be an LLMProvider, got {type(llm).__name__}")
        if not isinstance(top_k, int) or top_k <= 0:
            raise ValueError(f"Reranker: top_k must be a positive int, got {top_k!r}")
        if not documents:
            return []

        if reranker is not None:
            return await self._rerank_with_backend(query, documents, reranker, top_k)

        assert llm is not None  # narrowed: reranker is None implies llm was validated above
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
    async def _rerank_with_backend(
        query: str,
        documents: list[Mapping[str, Any]],
        reranker: RerankerBackend,
        top_k: int,
    ) -> list[Mapping[str, Any]]:
        """Rank ``documents`` by a backend's relevance scores and return the top-K.

        Args:
            query: The relevance reference query.
            documents: The documents to score and rank.
            reranker: The scoring backend.
            top_k: The maximum number of documents to return.

        Returns:
            Up to ``top_k`` documents ordered by descending backend score.
        """
        scores = await reranker.score(query, documents)
        ranked = sorted(
            zip(scores, range(len(documents)), documents, strict=True),
            key=lambda triple: (triple[0], -triple[1]),
            reverse=True,
        )
        return [doc for _, _, doc in ranked[:top_k]]

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
