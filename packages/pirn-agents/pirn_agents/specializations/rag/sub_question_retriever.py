"""``SubQuestionRetriever`` — concurrent per-sub-question retrieval + union.

The retrieval stage of sub-question RAG. Each sub-question is searched against
the :class:`MemoryStore` **concurrently** and the hits are unioned into a
single deduplicated context set, preserving the order in which documents were
first seen. Each surviving document records which ``sub_question`` first
retrieved it.

The fan-out is expressed as a graph rather than a hand-rolled
``asyncio.gather`` over a semaphore: each sub-question becomes its own
:class:`_SubQuestionSearch` invocation, fanned out with a core
:class:`~pirn.nodes.map_markers.Map`, and folded into the deduplicated union
with a :class:`~pirn.nodes.reduce_.Reduce`. The engine schedules the
per-sub-question searches concurrently — every ready sibling starts as its own
task (PIR-841) — so retrieval runs *through* the engine, with its own
``Result``, history record, and lineage per sub-question. Each search knot
carries a ``concurrency_group`` so a run-level
:class:`~pirn.core.concurrency.concurrency_limits.ConcurrencyLimits` can bound
in-flight searches; ``max_concurrency`` stays a validated, accepted parameter
recorded on that group (bounding a *container* knot's own inner run this way
is not yet enforced by core — see ``ConcurrencyLimits`` PIR-841 slice 2/3 —
so, until that lands, ``max_concurrency`` documents the intended budget rather
than strictly capping it).

Algorithm:
    1. Validate ``sub_questions`` (list), ``store`` (:class:`MemoryStore`),
       ``top_k`` and ``max_concurrency`` (positive ints).
    2. Fan out one :class:`_SubQuestionSearch` invocation per sub-question.
    3. A :class:`~pirn.nodes.reduce_.Reduce` unions the hits, keying by ``id``
       (or a stable fallback) so a document retrieved by several sub-questions
       appears once, in first-seen order.
    4. Return the deduplicated document list.

References:
    - Sub-question query engine pattern (LlamaIndex).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.map_markers import Map
from pirn.nodes.reduce_ import Reduce

from pirn_agents.interfaces.retriever import Retriever
from pirn_agents.memory.stores.memory_store import MemoryStore
from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.specializations.base.resolved_value_knot import ResolvedValueKnot


class _SubQuestionSearch(Knot):
    """Search the store for one sub-question and return its hits with provenance."""

    def __init__(
        self,
        *,
        sub_question: Knot | str,
        store: Knot | MemoryStore,
        top_k: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            sub_question=sub_question, store=store, top_k=top_k, _config=_config, **kwargs
        )

    async def process(
        self,
        sub_question: str,
        store: MemoryStore,
        top_k: int,
        **_: Any,
    ) -> tuple[str, list[Mapping[str, Any]]]:
        """Search ``store`` for ``sub_question`` and return its hits.

        Args:
            sub_question: The sub-question to search for.
            store: The memory store to search.
            top_k: Maximum number of hits to fetch.

        Returns:
            A ``(sub_question, hits)`` pair.
        """
        hits = [item async for item in await store.search(sub_question, top_k=top_k)]
        return sub_question, hits


class _UnionSubQuestionHits:
    """Reduce ``combine`` target: union per-sub-question hits, deduplicated."""

    @staticmethod
    def combine(items: list[tuple[str, list[Mapping[str, Any]]]]) -> list[Mapping[str, Any]]:
        """Union ``items`` into a single deduplicated, first-seen-order list.

        Args:
            items: ``(sub_question, hits)`` pairs, one per sub-question, in
                the sub-questions' original order.

        Returns:
            The deduplicated hits, each carrying which sub-question first
            retrieved it.
        """
        merged: dict[str, Mapping[str, Any]] = {}
        for sub_question, hits in items:
            for hit in hits:
                key = _UnionSubQuestionHits._doc_key(hit)
                if key not in merged:
                    enriched = dict(hit)
                    enriched.setdefault("sub_question", sub_question)
                    merged[key] = enriched
        return list(merged.values())

    @staticmethod
    def _doc_key(hit: Mapping[str, Any]) -> str:
        """Return a stable identity key for a retrieved hit."""
        identifier = hit.get("id")
        if identifier is not None:
            return str(identifier)
        return repr(sorted((str(k), str(v)) for k, v in hit.items()))


class SubQuestionRetriever(AgentPipeline, Retriever):
    """Retrieve per sub-question concurrently and union the deduplicated hits."""

    def __init__(
        self,
        *,
        sub_questions: Knot | list[str],
        store: Knot | MemoryStore,
        _config: KnotConfig,
        top_k: Knot | int = 3,
        max_concurrency: Knot | int = 4,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            sub_questions=sub_questions,
            store=store,
            top_k=top_k,
            max_concurrency=max_concurrency,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        sub_questions: list[str],
        store: MemoryStore,
        top_k: int = 3,
        max_concurrency: int = 4,
        **_: Any,
    ) -> Knot:
        """Build the per-sub-question search graph and return its union sink knot.

        Args:
            sub_questions: The sub-questions to search for.
            store: The memory store searched once per sub-question.
            top_k: Number of hits fetched per sub-question.
            max_concurrency: Intended in-flight search budget (see module
                docstring for the current enforcement caveat).

        Returns:
            The sink knot whose output is the deduplicated union of retrieved
            documents in first-seen order.

        Raises:
            TypeError: If ``store`` is not a MemoryStore or ``sub_questions`` not a list.
            ValueError: If ``top_k``/``max_concurrency`` are not positive ints.
        """
        if not isinstance(store, MemoryStore):
            raise TypeError(
                f"SubQuestionRetriever: store must be a MemoryStore, got {type(store).__name__}"
            )
        if not isinstance(sub_questions, list):
            raise TypeError(
                "SubQuestionRetriever: sub_questions must be a list, "
                f"got {type(sub_questions).__name__}"
            )
        if not isinstance(top_k, int) or top_k <= 0:
            raise ValueError(f"SubQuestionRetriever: top_k must be a positive int, got {top_k!r}")
        if not isinstance(max_concurrency, int) or max_concurrency <= 0:
            raise ValueError(
                "SubQuestionRetriever: max_concurrency must be a positive int, "
                f"got {max_concurrency!r}"
            )
        if not sub_questions:
            return ResolvedValueKnot(value=[], _config=KnotConfig(id="empty"))

        sub_questions_knot = ResolvedValueKnot(
            value=sub_questions, _config=KnotConfig(id="sub_questions")
        )
        searched = _SubQuestionSearch(
            # Core's Map marker is consumed at construction by
            # `knot.py:199-205` and is deliberately not a Knot, so it does not
            # satisfy the declared `Knot | str`. Inline suppression is the
            # house idiom for this; see PIR-715/PIR-716.
            sub_question=Map(sub_questions_knot),  # pyright: ignore[reportArgumentType]
            store=store,
            top_k=top_k,
            _config=KnotConfig(id="search_each", concurrency_group="sub_question_retriever_search"),
        )
        return Reduce(
            of=searched,
            combine=_UnionSubQuestionHits.combine,
            _config=KnotConfig(id="union"),
        )
