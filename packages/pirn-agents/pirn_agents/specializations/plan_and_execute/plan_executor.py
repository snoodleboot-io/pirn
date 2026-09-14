"""``PlanExecutor`` — executes each step of a Plan sequentially via LLM calls.

Each step's prompt includes every prior step's result as context, so the
loop genuinely depends on its own accumulated state and is wired as a
:class:`~pirn.nodes.loop_sub_tapestry.LoopSubTapestry` iteration
(:class:`~pirn_agents.specializations.plan_and_execute._plan_step_loop._PlanStepLoop`)
rather than a hand-rolled ``for`` loop awaiting ``llm.chat`` directly
(PIR-867).

Algorithm:
    1. Receive the resolved ``plan`` (:class:`Plan`) and ``llm`` (:class:`LLMProvider`).
    2. Seed a :class:`~pirn_agents.specializations.plan_and_execute._plan_step_state._PlanStepState`
       from ``plan.steps`` and build the iteration loop.
    3. Wire :class:`~pirn_agents.specializations.plan_and_execute._plan_execution_result._PlanExecutionResult`
       over the loop's final state and return it as the sink.

References:
    - Yao et al. (2023) "Tree of Thoughts: Deliberate Problem Solving with Large Language Models"
    - Wang et al. (2023) "Plan-and-Solve Prompting: Improving Zero-Shot Chain-of-Thought Reasoning"
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.planning.plan import Plan
from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.specializations.plan_and_execute._plan_execution_result import (
    _PlanExecutionResult,
)
from pirn_agents.specializations.plan_and_execute._plan_step_loop import _PlanStepLoop
from pirn_agents.specializations.plan_and_execute._plan_step_state import _PlanStepState


class PlanExecutor(AgentPipeline):
    """Take a :class:`Plan` and execute each step via sequential sub-LLM calls.

    Each step is executed in order. The context for step N includes the
    results of all prior steps so the LLM can build on previous outputs.
    All step outputs are concatenated into the final :class:`AgentResponse`.
    """

    def __init__(
        self,
        *,
        plan: Knot | Plan,
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(plan=plan, llm=llm, _config=_config, **kwargs)

    async def process(self, plan: Plan, llm: LLMProvider, **_: Any) -> Knot:
        """Wire the sequential step loop and return the sink knot.

        Args:
            plan: The Plan whose steps will be executed in order.
            llm: The LLM provider used to execute each step.

        Returns:
            The sink of the inner pipeline: a :class:`_PlanExecutionResult`
            over the loop's final state, whose output — an ``AgentResponse``
            whose content contains each step result separated by newlines —
            becomes this knot's output.
        """
        loop = _PlanStepLoop(
            llm=llm,
            state=_PlanStepState(steps=tuple(plan.steps)),
            _config=KnotConfig(id="loop"),
        )
        return _PlanExecutionResult(state=loop, _config=KnotConfig(id="result"))
