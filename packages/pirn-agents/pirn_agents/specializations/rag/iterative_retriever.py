"""``IterativeRetriever`` — bounded recursive retrieve-and-refine loop.

Iterative (a.k.a. recursive) retrieval retrieves, inspects what came back, and —
if the evidence looks incomplete — asks the LLM for a sharper follow-up query
and retrieves again. The loop is hard-bounded by ``max_iterations`` so it always
terminates, and accumulated hits are deduplicated across rounds.

The loop is expressed as an :class:`~pirn_agents.specializations.base.agent_loop_pipeline.AgentLoopPipeline`
rather than a hand-rolled ``for iteration in range(max_iterations)`` that
awaited ``memory.search`` and ``llm.chat`` directly: each round becomes its own
iteration tapestry with a :class:`_RetrievalRound` knot, a :class:`_MergeHits`
knot, and — on every iteration but the last — a :class:`_DecideFollowUp`
knot. Both termination decisions (whether more evidence is needed, and the
hard ``max_iterations`` cap) live inside the loop driver, per
``agent_loop_pipeline.py``; the follow-up decision is simply omitted from the
last iteration's tapestry, so it is never built and never paid for, rather
than being run and its result discarded.

Algorithm:
    1. Validate ``query`` (str), ``memory`` (:class:`MemoryStore`), ``llm``
       (:class:`LLMProvider`), ``max_iterations`` and ``top_k`` (positive ints).
    2. Start with ``current_query = query``. Each iteration:
       a. :class:`_RetrievalRound` searches ``memory`` for ``top_k`` hits.
       b. :class:`_MergeHits` unions them into the accumulated set (dedup by id).
       c. On every iteration but the last, :class:`_DecideFollowUp` asks the LLM
          to reply ``DONE`` (evidence sufficient) or ``REFINE: <follow-up
          query>``; on ``REFINE`` the loop continues with the new query, on
          anything else (or on the last iteration) it stops.
    3. Return the accumulated deduplicated documents.

References:
    - Asai et al., "Self-RAG" (2023): https://arxiv.org/abs/2310.11511
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_result import RunResult
from pirn.tapestry import Tapestry

from pirn_agents.interfaces.retriever import Retriever
from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.memory.stores.memory_store import MemoryStore
from pirn_agents.prompt.prompt_binding import PromptBinding
from pirn_agents.specializations.base.agent_loop_pipeline import AgentLoopPipeline
from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.specializations.llm_response_text import LlmResponseText


@dataclass
class _IterativeRetrievalState:
    """State threaded across retrieve-and-refine rounds."""

    original_query: str
    current_query: str
    merged: dict[str, Mapping[str, Any]] = field(default_factory=dict)
    iteration: int = 0
    done: bool = False


class _RetrievalRound(Knot):
    """Search the store for the current round's query."""

    def __init__(
        self,
        *,
        memory: Knot | MemoryStore,
        query: Knot | str,
        top_k: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(memory=memory, query=query, top_k=top_k, _config=_config, **kwargs)

    async def process(
        self,
        memory: MemoryStore,
        query: str,
        top_k: int,
        **_: Any,
    ) -> list[Mapping[str, Any]]:
        """Search ``memory`` for ``query`` and return up to ``top_k`` hits.

        Args:
            memory: The memory store to search.
            query: The current round's query.
            top_k: Maximum number of hits to fetch.

        Returns:
            The hits for this round.
        """
        return [item async for item in await memory.search(query, top_k=top_k)]


class _MergeHits(Knot):
    """Union this round's hits into the accumulated, deduplicated set."""

    def __init__(
        self,
        *,
        prior_merged: Knot | Mapping[str, Mapping[str, Any]],
        hits: Knot | list[Mapping[str, Any]],
        iteration: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            prior_merged=prior_merged, hits=hits, iteration=iteration, _config=_config, **kwargs
        )

    async def process(
        self,
        prior_merged: Mapping[str, Mapping[str, Any]],
        hits: list[Mapping[str, Any]],
        iteration: int,
        **_: Any,
    ) -> dict[str, Mapping[str, Any]]:
        """Merge ``hits`` into ``prior_merged``, keeping the first-seen mapping.

        Args:
            prior_merged: The accumulated set from earlier rounds.
            hits: This round's freshly retrieved hits.
            iteration: The current round index, recorded on newly-seen hits.

        Returns:
            The updated accumulated set.
        """
        merged = dict(prior_merged)
        for hit in hits:
            key = _MergeHits._doc_key(hit)
            if key not in merged:
                enriched = dict(hit)
                enriched.setdefault("iteration", iteration)
                merged[key] = enriched
        return merged

    @staticmethod
    def _doc_key(hit: Mapping[str, Any]) -> str:
        """Return a stable identity key for a retrieved hit."""
        identifier = hit.get("id")
        if identifier is not None:
            return str(identifier)
        return repr(sorted((str(k), str(v)) for k, v in hit.items()))


class _DecideFollowUp(Knot):
    """Ask the LLM whether more evidence is needed, and for what query."""

    def __init__(
        self,
        *,
        original_query: Knot | str,
        current_query: Knot | str,
        merged: Knot | Mapping[str, Mapping[str, Any]],
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            original_query=original_query,
            current_query=current_query,
            merged=merged,
            llm=llm,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        original_query: str,
        current_query: str,
        merged: Mapping[str, Mapping[str, Any]],
        llm: LLMProvider,
        **_: Any,
    ) -> str | None:
        """Ask the LLM to refine; return a follow-up query or ``None`` to stop."""
        return await IterativeRetriever._decide(llm, original_query, merged, current_query)


class _IterativeRetrievalLoop(AgentLoopPipeline[_IterativeRetrievalState]):
    """Drive the retrieve / merge / decide loop under a round budget."""

    def __init__(
        self,
        *,
        memory: MemoryStore,
        llm: LLMProvider,
        max_iterations: int,
        top_k: int,
        **kwargs: Any,
    ) -> None:
        self._memory = memory
        self._llm = llm
        self._max_iterations = max_iterations
        self._top_k = top_k
        super().__init__(**kwargs)

    def step(
        self, state: _IterativeRetrievalState
    ) -> tuple[Tapestry, _IterativeRetrievalState] | None:
        """Build the next round, or return None to terminate.

        Args:
            state: Accumulated state from the previous ``fold``.

        Returns:
            The round's tapestry paired with the state ``fold`` will receive,
            or ``None`` once the round budget is exhausted or the loop was
            told to stop.
        """
        if state.done or state.iteration >= self._max_iterations:
            return None
        is_last_round = state.iteration == self._max_iterations - 1

        with Tapestry() as t:
            hits = _RetrievalRound(
                memory=self._memory,
                query=state.current_query,
                top_k=self._top_k,
                _config=KnotConfig(id="search"),
            )
            merged = _MergeHits(
                prior_merged=state.merged,
                hits=hits,
                iteration=state.iteration,
                _config=KnotConfig(id="merge"),
            )
            if not is_last_round:
                _DecideFollowUp(
                    original_query=state.original_query,
                    current_query=state.current_query,
                    merged=merged,
                    llm=self._llm,
                    _config=KnotConfig(id="decide"),
                )
        return t, state

    def fold(self, state: _IterativeRetrievalState, result: RunResult) -> _IterativeRetrievalState:
        """Integrate one round's outputs into a new state.

        Args:
            state: State as ``step`` returned it.
            result: The round's run result.

        Returns:
            A new state carrying the round's merged hits and next query.
        """
        merged = result.outputs["merge"]
        # Absent on the last round (no _DecideFollowUp was built) or when the
        # LLM's reply was not a REFINE instruction. Either way, stop.
        follow_up = result.outputs.get("decide")
        return _IterativeRetrievalState(
            original_query=state.original_query,
            current_query=follow_up if follow_up is not None else state.current_query,
            merged=merged,
            iteration=state.iteration + 1,
            done=follow_up is None,
        )

    def step_id(self, state: _IterativeRetrievalState, idx: int) -> str:
        """Name each round for run history."""
        return f"round_{idx}"


class _IterativeRetrievalResult(Knot):
    """Extract the accumulated document list from the loop's final state."""

    def __init__(
        self,
        *,
        state: Knot | _IterativeRetrievalState,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(state=state, _config=_config, **kwargs)

    async def process(self, state: _IterativeRetrievalState, **_: Any) -> list[Mapping[str, Any]]:
        """Return the deduplicated union of documents accumulated across rounds."""
        return list(state.merged.values())


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
