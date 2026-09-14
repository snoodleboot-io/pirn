"""``_PlanStepLoop`` — drive the sequential plan-step execution loop.

Each step's prompt includes every prior step's result, so steps cannot be
fanned out independently — the loop genuinely depends on its own accumulated
state, which is exactly the shape :class:`~pirn.nodes.loop_sub_tapestry.LoopSubTapestry`
exists for (PIR-867; see the module docstring on
:class:`~pirn_agents.specializations.base.agent_loop_pipeline.AgentLoopPipeline`).
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.run_result import RunResult
from pirn.tapestry import Tapestry

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.specializations.base.agent_loop_pipeline import AgentLoopPipeline
from pirn_agents.specializations.plan_and_execute._plan_step_call import _PlanStepCall
from pirn_agents.specializations.plan_and_execute._plan_step_state import _PlanStepState


class _PlanStepLoop(AgentLoopPipeline[_PlanStepState]):
    """Execute a plan's steps in order, threading each step's result forward."""

    def __init__(self, *, llm: LLMProvider, **kwargs: Any) -> None:
        self._llm = llm
        super().__init__(**kwargs)

    def step(self, state: _PlanStepState) -> tuple[Tapestry, _PlanStepState] | None:
        """Build the next step's call, or return ``None`` once every step has run.

        Args:
            state: Accumulated state from the previous ``fold``.

        Returns:
            The step's tapestry paired with the state ``fold`` will receive,
            or ``None`` once every step in the plan has executed.
        """
        if state.index >= len(state.steps):
            return None
        with Tapestry() as t:
            _PlanStepCall(
                step_index=state.index,
                step_text=state.steps[state.index],
                prior_results=state.step_results,
                llm=self._llm,
                _config=KnotConfig(id="call"),
            )
        return t, state

    def fold(self, state: _PlanStepState, result: RunResult) -> _PlanStepState:
        """Append the completed step's result and advance to the next index.

        Args:
            state: State as ``step`` returned it.
            result: The step's run result.

        Returns:
            A new state carrying the step's result and the next index.
        """
        return _PlanStepState(
            steps=state.steps,
            step_results=(*state.step_results, result.outputs["call"]),
            index=state.index + 1,
        )

    def step_id(self, state: _PlanStepState, idx: int) -> str:
        """Name each iteration for run history."""
        return f"step_{idx}"
