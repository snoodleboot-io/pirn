"""``_IterativeRetrievalLoop`` — drive the retrieve/merge/decide loop."""

from __future__ import annotations

from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.run_result import RunResult
from pirn.tapestry import Tapestry

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.memory.stores.memory_store import MemoryStore
from pirn_agents.specializations.base.agent_loop_pipeline import AgentLoopPipeline
from pirn_agents.specializations.rag._decide_follow_up import _DecideFollowUp
from pirn_agents.specializations.rag._iterative_retrieval_state import _IterativeRetrievalState
from pirn_agents.specializations.rag._merge_hits import _MergeHits
from pirn_agents.specializations.rag._retrieval_round import _RetrievalRound


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
