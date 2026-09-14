"""``AgenticRagLoop`` — drive the tool-call/follow-up-decision loop."""

from __future__ import annotations

from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.run_result import RunResult
from pirn.tapestry import Tapestry

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.specializations.base.agent_loop_pipeline import AgentLoopPipeline
from pirn_agents.specializations.rag.agentic_rag_state import AgenticRagState
from pirn_agents.specializations.rag.follow_up_decision import FollowUpDecision
from pirn_agents.tools.tool_call import ToolCall
from pirn_agents.tools.tool_factory import ToolFactory
from pirn_agents.tools.tool_invocation import ToolInvocation
from pirn_agents.tools.tool_result import ToolResult


class AgenticRagLoop(AgentLoopPipeline[AgenticRagState]):
    """Drive the tool-call / follow-up-decision loop under a round budget."""

    def __init__(
        self,
        *,
        query: str,
        rag_tool: ToolFactory,
        llm: LLMProvider,
        max_iterations: int,
        **kwargs: Any,
    ) -> None:
        self._query = query
        self._rag_tool = rag_tool
        self._llm = llm
        self._max_iterations = max_iterations
        super().__init__(**kwargs)

    def step(self, state: AgenticRagState) -> tuple[Tapestry, AgenticRagState] | None:
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
            call = ToolCall(
                tool_name=self._rag_tool.name,
                arguments={"question": state.current_question},
                call_id=f"agentic_rag_{state.iteration}",
            )
            invoke = ToolInvocation(tool=self._rag_tool, call=call, _config=KnotConfig(id="call"))
            if not is_last_round:
                FollowUpDecision(
                    original_query=self._query,
                    tool_result=invoke,
                    llm=self._llm,
                    _config=KnotConfig(id="decide"),
                )
        return t, state

    def fold(self, state: AgenticRagState, result: RunResult) -> AgenticRagState:
        """Integrate one round's outputs into a new state.

        Args:
            state: State as ``step`` returned it.
            result: The round's run result.

        Returns:
            A new state carrying the round's answer and next question.

        Raises:
            RuntimeError: If the tool call itself failed.
        """
        tool_result: ToolResult = result.outputs["call"]
        if not tool_result.succeeded:
            raise RuntimeError(f"AgenticRagPipeline: rag_tool call failed: {tool_result.error}")
        answer = FollowUpDecision.tool_answer(tool_result.result)
        # Absent on the last round (no FollowUpDecision was built) or when the
        # LLM's reply was not a FOLLOWUP instruction. Either way, stop.
        follow_up = result.outputs.get("decide")
        return AgenticRagState(
            current_question=follow_up if follow_up is not None else state.current_question,
            answer=answer,
            iteration=state.iteration + 1,
            done=follow_up is None,
        )

    def step_id(self, state: AgenticRagState, idx: int) -> str:
        """Name each round for run history."""
        return f"round_{idx}"
