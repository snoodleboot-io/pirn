"""``SubQuestionRetriever`` — concurrent per-sub-question retrieval + union.

The retrieval stage of sub-question RAG. Each sub-question is searched against
the :class:`MemoryStore` **concurrently** and the hits are unioned into a
single deduplicated context set, preserving the order in which documents were
first seen. Each surviving document records which ``sub_question`` first
retrieved it.

The fan-out is expressed as a graph rather than a hand-rolled
``asyncio.gather`` over a semaphore: one
:class:`~pirn_agents.specializations.rag.sub_question_search.SubQuestionSearch`
knot per sub-question, wired into an
:class:`~pirn.nodes.aggregator.Aggregator` that unions their hits. The engine
schedules ready siblings concurrently (PIR-841), so every sub-question's
search gets its own ``Result``, history record, lineage row and admission
slot.

Every search knot carries the same ``concurrency_group`` and
``max_concurrency`` is that group's cap: ``process()`` declares it through
:class:`~pirn_agents.specializations.base.inner_group_limit.InnerGroupLimit`
and ``_inner_concurrency()`` hands it to the inner run, the lever
:class:`~pirn_agents.batch.map_agent.MapAgent` and
:class:`~pirn_agents.specializations.document_processing.ingestion_runner.IngestionRunner`
use. Until PIR-873 the fan-out was a single knot with a core
:class:`~pirn.core.map.Map` marker, whose per-element invocations are one
``asyncio.gather`` *inside* that knot: they shared one lineage row and one
admission slot, so the group cap could not bound them and
``max_concurrency`` was validated and then discarded behind a docstring
claiming core could not enforce it.

Algorithm:
    1. Validate ``sub_questions`` (list), ``store`` (:class:`MemoryStore`),
       ``top_k`` and ``max_concurrency`` (positive ints).
    2. Declare the search group's cap from ``max_concurrency``.
    3. Build one ``SubQuestionSearch`` knot per sub-question, all in that group.
    4. An :class:`~pirn.nodes.aggregator.Aggregator` unions the hits, keying by
       ``id`` (or a stable fallback) so a document retrieved by several
       sub-questions appears once, in first-seen order.
    5. Return the deduplicated document list.

References:
    - Sub-question query engine pattern (LlamaIndex).
"""

from __future__ import annotations

import functools
from typing import Any, ClassVar

from pirn.core.concurrency.concurrency_limits import ConcurrencyLimits
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.nodes.aggregator import Aggregator

from pirn_agents.interfaces.retriever import Retriever
from pirn_agents.memory.stores.memory_store import MemoryStore
from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.specializations.base.inner_group_limit import InnerGroupLimit
from pirn_agents.specializations.rag.sub_question_search import SubQuestionSearch
from pirn_agents.specializations.rag.union_sub_question_hits import UnionSubQuestionHits


class SubQuestionRetriever(AgentPipeline, Retriever):
    """Retrieve per sub-question concurrently and union the deduplicated hits."""

    #: Per-run carrier for the search group's cap (never instance state).
    _group_limit: ClassVar[InnerGroupLimit] = InnerGroupLimit("sub_question_retriever_search")

    def _inner_concurrency(self) -> ConcurrencyLimits | None:
        """This run's search-group cap, or ``None`` when no search runs.

        Read by ``SubTapestry._run_inner`` after ``process()`` has declared it;
        the cap rides the run's own context, never this shared knot.
        """
        return type(self)._group_limit.current()

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
            max_concurrency: Maximum searches in flight at once; the cap on
                the searches' concurrency group.

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
        type(self)._group_limit.declare(members=len(sub_questions), max_concurrency=max_concurrency)
        if not sub_questions:
            return Parameter("empty", list[Any], default=[], _config=KnotConfig(id="empty"))

        searches: dict[str, Knot] = {
            f"search_{index}": SubQuestionSearch(
                sub_question=sub_question,
                store=store,
                top_k=top_k,
                _config=KnotConfig(
                    id=f"search_{index}",
                    concurrency_group=type(self)._group_limit.group,
                ),
            )
            for index, sub_question in enumerate(sub_questions)
        }
        return Aggregator(
            combine=functools.partial(UnionSubQuestionHits.aggregate, len(sub_questions)),
            _config=KnotConfig(id="union"),
            **searches,
        )
