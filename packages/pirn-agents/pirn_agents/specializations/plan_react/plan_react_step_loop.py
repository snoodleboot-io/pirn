"""``PlanReActStepLoop`` — run one ReAct loop per plan step, in order.

The steps are sequential by design: a plan is ordered, and each step's ReAct loop
calls tools, so their side effects must not interleave. That makes this a genuine
``LoopSubTapestry`` rather than a chain or a fan-out — the iteration is core's, and
each step is one traceable iteration inside one run, with its own ``Result``,
history record and lineage.

It replaces a hand-rolled ``for step in steps: await self._run_inner(...)``, which
paid one engine round trip per step and left each step's lineage in an unrelated
run (knot-design-rules Rule 11; PIR-874).

Internal API.
"""

from __future__ import annotations

from typing import Any, ClassVar

from pirn.core.knot_config import KnotConfig
from pirn.core.run_result import RunResult
from pirn.tapestry import Tapestry

from pirn_agents.specializations.base.agent_loop_pipeline import AgentLoopPipeline
from pirn_agents.specializations.plan_react.plan_react_step_state import PlanReActStepState
from pirn_agents.specializations.react.react_loop import ReActLoop
from pirn_agents.types.messaging.agent_message import AgentMessage
from pirn_agents.types.messaging.agent_response import AgentResponse


class PlanReActStepLoop(AgentLoopPipeline[PlanReActStepState]):
    """Run each plan step's ReAct loop in order, collecting the responses."""

    #: Per-iteration knot id (Rule: no module-level constants).
    _react_id: ClassVar[str] = "pr_react"

    def step(self, state: PlanReActStepState) -> tuple[Tapestry, PlanReActStepState] | None:
        """Build the next step's ReAct loop, or ``None`` once every step has run.

        Args:
            state: Accumulated state from the previous ``fold``.

        Returns:
            The step's tapestry paired with the state ``fold`` will receive, or
            ``None`` once ``state.index`` has walked past the last step.
        """
        if state.index >= len(state.steps):
            return None
        with Tapestry() as iteration:
            ReActLoop(
                messages=(AgentMessage(role="user", content=state.steps[state.index]),),
                llm=state.llm,
                tools=state.tools,
                max_iterations=state.max_iterations,
                _config=KnotConfig(id=type(self)._react_id),
            )
        return iteration, state

    def fold(self, state: PlanReActStepState, result: RunResult) -> PlanReActStepState:
        """Collect this step's response and advance to the next step.

        A step whose loop produced something other than an ``AgentResponse`` is
        recorded as one built from its string form, exactly as the hand-rolled
        version did.

        Args:
            state: State as ``step`` returned it.
            result: The step's run result.

        Returns:
            A new state carrying the response and the next index.
        """
        raw: Any = result.outputs[type(self)._react_id]
        response = raw if isinstance(raw, AgentResponse) else AgentResponse(content=str(raw))
        return PlanReActStepState(
            steps=state.steps,
            llm=state.llm,
            tools=state.tools,
            max_iterations=state.max_iterations,
            responses=(*state.responses, response),
            index=state.index + 1,
        )

    def step_id(self, state: PlanReActStepState, idx: int) -> str:
        """Name each step for run history."""
        return f"step_{idx}"
