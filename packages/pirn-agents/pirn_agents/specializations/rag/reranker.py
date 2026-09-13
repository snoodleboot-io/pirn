"""``Reranker`` — LLM-based relevance re-ranking of retrieved documents.

Takes a list of retrieved documents and a query, scores the relevance of each
document, and returns the top-K reranked documents. Two interchangeable
scoring backings are supported: the default LLM path (one
:class:`_DocumentRelevanceScorer` invocation per document) and a
provider-neutral :class:`~pirn_agents.retrieval.rerank.reranker_backend.RerankerBackend`
(e.g. the cross-encoder adapter) injected via ``reranker``.

The LLM path is expressed as a graph rather than a hand-rolled
``for doc in documents: await llm.chat(...)`` loop: each document becomes its
own :class:`_DocumentRelevanceScorer` invocation, fanned out with a core
:class:`~pirn.nodes.map_markers.Map`, and folded back into the top-K list with
a :class:`~pirn.nodes.reduce_.Reduce`. The engine schedules the per-document
scorers concurrently — every ready sibling starts as its own task (PIR-841) —
so scoring runs *through* the engine, with its own ``Result``, history record,
and lineage per document.

Algorithm:
    1. Receive ``query`` string, ``documents`` list of Mappings, ``llm``
       provider or ``reranker`` backend, and ``top_k`` integer.
    2. Validate inputs: ``query`` must be a string, exactly one of ``llm`` /
       ``reranker`` must be provided, ``top_k`` a positive integer.
    3. If ``documents`` is empty, return ``[]`` immediately (as a real graph
       node, via :class:`~pirn_agents.specializations.base.resolved_value_knot.ResolvedValueKnot`).
    4. Backend path — a single :class:`_BackendRerank` invocation scores every
       document in one call.
    5. LLM path — one :class:`_DocumentRelevanceScorer` invocation per document,
       fanned out with ``Map``; each parses its LLM reply as a float in
       [0.0, 1.0], defaulting to 0.0 on parse error.
    6. A :class:`~pirn.nodes.reduce_.Reduce` sorts the ``(score, document)``
       pairs descending by score and keeps the top ``top_k``.

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

import functools
from collections.abc import Mapping
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.map_markers import Map
from pirn.nodes.reduce_ import Reduce

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.prompt.prompt_binding import PromptBinding
from pirn_agents.retrieval.rerank.reranker_backend import RerankerBackend
from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.specializations.base.resolved_value_knot import ResolvedValueKnot
from pirn_agents.specializations.llm_response_text import LlmResponseText


class _DocumentRelevanceScorer(Knot):
    """Score one document's relevance to the query via the LLM.

    Algorithm:
        1. Render the score prompt from ``query`` and the document's text.
        2. Call the LLM and extract plain text from its response.
        3. Parse the reply as a float; default to 0.0 on parse error so a
           malformed reply drops the document to the bottom of the ranking
           instead of failing the whole rerank.

    Math:
        Relevance score :math:`s \\in [0.0, 1.0]` for one document, as judged
        by the LLM from its free-text reply.
    """

    _score_prompt: ClassVar[PromptBinding] = PromptBinding(
        name="specializations.rag.reranker.score_prompt",
        default=(
            "Score the relevance of the following document to the query "
            "on a scale from 0.0 (not relevant) to 1.0 (highly relevant). "
            "Reply with only the numeric score.\n\n"
            "Query: {{ query }}\n\nDocument: {{ text }}"
        ),
    )

    def __init__(
        self,
        *,
        query: Knot | str,
        document: Knot | Mapping[str, Any],
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(query=query, document=document, llm=llm, _config=_config, **kwargs)

    async def process(
        self,
        query: str,
        document: Mapping[str, Any],
        llm: LLMProvider,
        **_: Any,
    ) -> tuple[float, Mapping[str, Any]]:
        """Score ``document``'s relevance to ``query``.

        Args:
            query: The relevance reference query.
            document: The document mapping to score.
            llm: The provider asked to score relevance.

        Returns:
            A ``(score, document)`` pair, ``score`` defaulting to 0.0 when the
            LLM's reply does not parse as a float.
        """
        text = _DocumentRelevanceScorer._doc_text(document)
        prompt = _DocumentRelevanceScorer._score_prompt.render({"query": query, "text": text})
        raw = await llm.chat([{"role": "user", "content": prompt}])
        score_text = LlmResponseText().extract(raw).strip()
        try:
            score = float(score_text)
        except ValueError:
            score = 0.0
        return score, document

    @staticmethod
    def _doc_text(doc: Mapping[str, Any]) -> str:
        parts: list[str] = []
        for value in doc.values():
            parts.append(value if isinstance(value, str) else str(value))
        return " ".join(parts)


class _TopKByScore:
    """Reduce ``combine`` target: pick the top-K ``(score, document)`` pairs."""

    @staticmethod
    def combine(
        items: list[tuple[float, Mapping[str, Any]]], *, top_k: int
    ) -> list[Mapping[str, Any]]:
        """Sort ``items`` by descending score and keep the top ``top_k`` documents.

        Args:
            items: ``(score, document)`` pairs, one per scored document.
            top_k: Maximum number of documents to keep.

        Returns:
            Up to ``top_k`` documents ordered by descending score.
        """
        ranked = sorted(items, key=lambda pair: pair[0], reverse=True)
        return [doc for _, doc in ranked[:top_k]]


class _BackendRerank(Knot):
    """Rank documents with a provider-neutral :class:`RerankerBackend` in one call."""

    def __init__(
        self,
        *,
        query: Knot | str,
        documents: Knot | list[Mapping[str, Any]],
        reranker: Knot | RerankerBackend,
        top_k: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            query=query,
            documents=documents,
            reranker=reranker,
            top_k=top_k,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        query: str,
        documents: list[Mapping[str, Any]],
        reranker: RerankerBackend,
        top_k: int,
        **_: Any,
    ) -> list[Mapping[str, Any]]:
        """Score ``documents`` with ``reranker`` and return the top ``top_k``.

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


class Reranker(AgentPipeline):
    """Score retrieved documents by relevance and return top-K reranked.

    Two interchangeable scoring backings are supported: the default LLM path
    (score each document with an :class:`LLMProvider`, fanned out over a
    :class:`_DocumentRelevanceScorer` per document) and a provider-neutral
    :class:`~pirn_agents.retrieval.rerank.reranker_backend.RerankerBackend` (e.g. the
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
    ) -> Knot:
        """Build the scoring graph and return its top-K-selecting sink knot.

        Args:
            query: The query string used as the relevance reference.
            documents: The list of retrieved document Mappings to score.
            llm: The LLMProvider used to score each document (LLM path).
            reranker: A provider-neutral scoring backend used instead of the
                LLM when supplied.
            top_k: The maximum number of documents to return.

        Returns:
            The sink knot whose output is up to ``top_k`` reranked documents.

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
            return ResolvedValueKnot(value=[], _config=KnotConfig(id="empty"))

        if reranker is not None:
            return _BackendRerank(
                query=query,
                documents=documents,
                reranker=reranker,
                top_k=top_k,
                _config=KnotConfig(id="backend_rerank"),
            )

        assert llm is not None  # narrowed: reranker is None implies llm was validated above
        documents_knot = ResolvedValueKnot(value=documents, _config=KnotConfig(id="documents"))
        scored = _DocumentRelevanceScorer(
            query=query,
            # Core's Map marker is consumed at construction by
            # `knot.py:199-205` and is deliberately not a Knot, so it does not
            # satisfy the declared `Knot | Mapping`. Inline suppression is the
            # house idiom for this; see PIR-715/PIR-716.
            document=Map(documents_knot),  # pyright: ignore[reportArgumentType]
            llm=llm,
            _config=KnotConfig(id="score_each"),
        )
        return Reduce(
            of=scored,
            combine=functools.partial(_TopKByScore.combine, top_k=top_k),
            _config=KnotConfig(id="top_k"),
        )
