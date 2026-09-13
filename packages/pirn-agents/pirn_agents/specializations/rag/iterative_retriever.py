"""``IterativeRetriever`` — bounded recursive retrieve-and-refine loop.

Iterative (a.k.a. recursive) retrieval retrieves, inspects what came back, and —
if the evidence looks incomplete — asks the LLM for a sharper follow-up query
and retrieves again. The loop is hard-bounded by ``max_iterations`` so it always
terminates, and accumulated hits are deduplicated across rounds.

The loop is expressed as an :class:`~pirn_agents.specializations.base.agent_loop_pipeline.AgentLoopPipeline`
(see :class:`~pirn_agents.specializations.rag._iterative_retrieval_loop._IterativeRetrievalLoop`)
rather than a hand-rolled ``for iteration in range(max_iterations)`` that
awaited ``memory.search`` and ``llm.chat`` directly: each round becomes its own
iteration tapestry with a ``_RetrievalRound`` knot, a ``_MergeHits``
knot, and — on every iteration but the last — a ``_DecideFollowUp``
knot. Both termination decisions (whether more evidence is needed, and the
hard ``max_iterations`` cap) live inside the loop driver, per
``agent_loop_pipeline.py``; the follow-up decision is simply omitted from the
last iteration's tapestry, so it is never built and never paid for, rather
than being run and its result discarded.

Algorithm:
    1. Validate ``query`` (str), ``memory`` (:class:`MemoryStore`), ``llm``
       (:class:`LLMProvider`), ``max_iterations`` and ``top_k`` (positive ints).
    2. Start with ``current_query = query``. Each iteration:
       a. ``_RetrievalRound`` searches ``memory`` for ``top_k`` hits.
       b. ``_MergeHits`` unions them into the accumulated set (dedup by id).
       c. On every iteration but the last, ``_DecideFollowUp`` asks the LLM
          to reply ``DONE`` (evidence sufficient) or ``REFINE: <follow-up
          query>``; on ``REFINE`` the loop continues with the new query, on
          anything else (or on the last iteration) it stops.
    3. Return the accumulated deduplicated documents.

References:
    - Asai et al., "Self-RAG" (2023): https://arxiv.org/abs/2310.11511
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.interfaces.retriever import Retriever
from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.memory.stores.memory_store import MemoryStore
from pirn_agents.prompt.prompt_binding import PromptBinding
from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.specializations.llm_response_text import LlmResponseText
from pirn_agents.specializations.rag._iterative_retrieval_loop import _IterativeRetrievalLoop
from pirn_agents.specializations.rag._iterative_retrieval_result import _IterativeRetrievalResult
from pirn_agents.specializations.rag._iterative_retrieval_state import _IterativeRetrievalState


class IterativeRetriever(AgentPipeline, Retriever):
    """Retrieve, ask the LLM whether to refine, and loop under a budget."""

    _decide_prompt: ClassVar[PromptBinding] = PromptBinding(
        name="specializations.rag.iterative_retriever.decide_prompt",
        default=(
            "You are running iterative retrieval. Given the original question and the "
            "evidence gathered so far, reply with exactly 'DONE' if the evidence is "
            "sufficient, or 'REFINE: <a sharper follow-up search query>' if more is "
            "needed.\n\nOriginal question: {{ original_query }}\n"
            "Last query: {{ current_query }}\n\nEvidence:\n{{ context }}"
        ),
    )

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

        loop = _IterativeRetrievalLoop(
            memory=memory,
            llm=llm,
            max_iterations=max_iterations,
            top_k=top_k,
            state=_IterativeRetrievalState(original_query=query, current_query=query),
            _config=KnotConfig(id="loop"),
        )
        return _IterativeRetrievalResult(state=loop, _config=KnotConfig(id="result"))

    @staticmethod
    async def _decide(
        llm: LLMProvider,
        original_query: str,
        merged: Mapping[str, Mapping[str, Any]],
        current_query: str,
    ) -> str | None:
        """Ask the LLM to refine; return a follow-up query or ``None`` to stop."""
        context = "\n".join(str(doc) for doc in merged.values()) or "(nothing yet)"
        prompt = IterativeRetriever._decide_prompt.render(
            {
                "original_query": original_query,
                "current_query": current_query,
                "context": context,
            }
        )
        raw = await llm.chat([{"role": "user", "content": prompt}])
        reply = LlmResponseText().extract(raw).strip()
        if reply.upper().startswith("REFINE:"):
            follow_up = reply.split(":", 1)[1].strip()
            return follow_up or None
        return None
