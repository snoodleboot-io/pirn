"""``IterativeRetriever`` — bounded recursive retrieve-and-refine loop.

Iterative (a.k.a. recursive) retrieval retrieves, inspects what came back, and —
if the evidence looks incomplete — asks the LLM for a sharper follow-up query
and retrieves again. The loop is hard-bounded by ``max_iterations`` so it always
terminates, and accumulated hits are deduplicated across rounds.

The loop is expressed as an :class:`~pirn_agents.specializations.base.agent_loop_pipeline.AgentLoopPipeline`
(see :class:`~pirn_agents.specializations.rag.iterative_retrieval_loop.IterativeRetrievalLoop`)
rather than a hand-rolled ``for iteration in range(max_iterations)`` that
awaited ``memory.search`` and ``llm.chat`` directly: each round becomes its own
iteration tapestry with a ``RetrievalRound`` knot, a ``MergeHits``
knot, and — on every iteration but the last — a ``DecideFollowUp``
knot. Both termination decisions (whether more evidence is needed, and the
hard ``max_iterations`` cap) live inside the loop driver, per
``agent_loop_pipeline.py``; the follow-up decision is simply omitted from the
last iteration's tapestry, so it is never built and never paid for, rather
than being run and its result discarded.

Algorithm:
    1. Validate ``query`` (str), ``memory`` (:class:`MemoryStore`), ``llm``
       (:class:`LLMProvider`), ``max_iterations`` and ``top_k`` (positive ints).
    2. Start with ``current_query = query``. Each iteration:
       a. ``RetrievalRound`` searches ``memory`` for ``top_k`` hits.
       b. ``MergeHits`` unions them into the accumulated set (dedup by id).
       c. On every iteration but the last, ``DecideFollowUp`` asks the LLM
          to reply ``DONE`` (evidence sufficient) or ``REFINE: <follow-up
          query>``; on ``REFINE`` the loop continues with the new query, on
          anything else (or on the last iteration) it stops.
    3. Return the accumulated deduplicated documents.

References:
    - Asai et al., "Self-RAG" (2023): https://arxiv.org/abs/2310.11511
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.interfaces.retriever import Retriever
from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.memory.stores.memory_store import MemoryStore
from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.specializations.rag.iterative_retrieval_loop import IterativeRetrievalLoop
from pirn_agents.specializations.rag.iterative_retrieval_result import IterativeRetrievalResult
from pirn_agents.specializations.rag.iterative_retrieval_state import IterativeRetrievalState


class IterativeRetriever(AgentPipeline, Retriever):
    """Retrieve, ask the LLM whether to refine, and loop under a budget."""

    def __init__(
        self,
        *,
        query: Knot | str,
        memory: Knot | MemoryStore,
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        max_iterations: Knot | int = 3,
        top_k: Knot | int = 3,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            query=query,
            memory=memory,
            llm=llm,
            max_iterations=max_iterations,
            top_k=top_k,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        query: str,
        memory: MemoryStore,
        llm: LLMProvider,
        max_iterations: int = 3,
        top_k: int = 3,
        **_: Any,
    ) -> Knot:
        """Build the retrieve-and-refine loop and return its result-extracting sink knot.

        Args:
            query: The initial query.
            memory: The memory store searched each round.
            llm: The provider deciding whether to refine.
            max_iterations: Hard upper bound on retrieval rounds (>= 1).
            top_k: Hits fetched per round.

        Returns:
            The sink knot whose output is the deduplicated union of documents
            retrieved across rounds.

        Raises:
            TypeError: If ``query``/``memory``/``llm`` are the wrong type.
            ValueError: If ``max_iterations``/``top_k`` are not positive ints.
        """
        if not isinstance(query, str):
            raise TypeError(
                f"IterativeRetriever: query must be a string, got {type(query).__name__}"
            )
        if not isinstance(memory, MemoryStore):
            raise TypeError(
                f"IterativeRetriever: memory must be a MemoryStore, got {type(memory).__name__}"
            )
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                f"IterativeRetriever: llm must be an LLMProvider, got {type(llm).__name__}"
            )
        if not isinstance(max_iterations, int) or max_iterations <= 0:
            raise ValueError(
                f"IterativeRetriever: max_iterations must be a positive int, got {max_iterations!r}"
            )
        if not isinstance(top_k, int) or top_k <= 0:
            raise ValueError(f"IterativeRetriever: top_k must be a positive int, got {top_k!r}")

        loop = IterativeRetrievalLoop(
            memory=memory,
            llm=llm,
            max_iterations=max_iterations,
            top_k=top_k,
            state=IterativeRetrievalState(original_query=query, current_query=query),
            _config=KnotConfig(id="loop"),
        )
        return IterativeRetrievalResult(state=loop, _config=KnotConfig(id="result"))
