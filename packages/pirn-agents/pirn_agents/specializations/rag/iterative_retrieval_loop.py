"""``IterativeRetrievalLoop`` — drive the retrieve/merge/decide loop."""

from __future__ import annotations

from dataclasses import replace

from pirn.core.knot_config import KnotConfig
from pirn.core.run_result import RunResult
from pirn.tapestry import Tapestry

from pirn_agents.specializations.base.agent_loop_pipeline import AgentLoopPipeline
from pirn_agents.specializations.rag.decide_follow_up import DecideFollowUp
from pirn_agents.specializations.rag.iterative_retrieval_state import IterativeRetrievalState
from pirn_agents.specializations.rag.merge_hits import MergeHits
from pirn_agents.specializations.rag.retrieval_round import RetrievalRound


class IterativeRetrievalLoop(AgentLoopPipeline[IterativeRetrievalState]):
    """Drive the retrieve / merge / decide loop under a round budget."""

    def step(
        self, state: IterativeRetrievalState
    ) -> tuple[Tapestry, IterativeRetrievalState] | None:
        """Build the next round, or return None to terminate.

        Args:
            state: Accumulated state from the previous ``fold``.

        Returns:
            The round's tapestry paired with the state ``fold`` will receive,
            or ``None`` once the round budget is exhausted or the loop was
            told to stop.
        """
        if state.done or state.iteration >= state.max_iterations:
            return None

        with Tapestry() as t:
            hits = RetrievalRound(
                memory=state.memory,
                query=state.current_query,
                top_k=state.top_k,
                _config=KnotConfig(id="search"),
            )
            merged = MergeHits(
                prior_merged=state.merged,
                hits=hits,
                iteration=state.iteration,
                _config=KnotConfig(id="merge"),
            )
            if not state.is_last_round():
                DecideFollowUp(
                    original_query=state.original_query,
                    current_query=state.current_query,
                    merged=merged,
                    llm=state.llm,
                    _config=KnotConfig(id="decide"),
                )
        return t, state

    def fold(self, state: IterativeRetrievalState, result: RunResult) -> IterativeRetrievalState:
        """Integrate one round's outputs into a new state.

        Args:
            state: State as ``step`` returned it.
            result: The round's run result.

        Returns:
            A new state carrying the round's merged hits and next query.
        """
        merged = result.outputs["merge"]
        # Absent on the last round (no DecideFollowUp was built) or when the
        # LLM's reply was not a REFINE instruction. Either way, stop.
        follow_up = result.outputs.get("decide")
        return replace(
            state,
            current_query=follow_up if follow_up is not None else state.current_query,
            merged=merged,
            iteration=state.iteration + 1,
            done=follow_up is None,
        )

    def step_id(self, state: IterativeRetrievalState, idx: int) -> str:
        """Name each round for run history."""
        return f"round_{idx}"
