"""``PlanReActPipeline`` — compose TaskPlanner then a ReActLoop per plan step.

A :class:`SubTapestry` that is a pure composition of two existing knots:

1. :class:`~pirn_agents.specializations.plan_and_execute.task_planner.TaskPlanner`
   decomposes the goal into ordered steps.
2. For each step (bounded by ``max_steps``) a
   :class:`~pirn_agents.specializations.react.react_loop.ReActLoop` runs with the
   step as its prompt; its :class:`AgentResponse` is collected.

Returns a typed :class:`PlanReActResult`; the final step's response is the overall
answer. Each per-step ReAct loop is itself bounded by ``max_iterations``.

References:
    - Yao et al. (2023) "ReAct" https://arxiv.org/abs/2210.03629
    - Wang et al. (2023) "Plan-and-Solve Prompting"
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.providers.llm_provider import LLMProvider
from pirn.nodes.source import Source
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry

from pirn_agents.specializations.plan_and_execute.task_planner import TaskPlanner
from pirn_agents.specializations.plan_react.plan_react_result import PlanReActResult
from pirn_agents.specializations.react.react_loop import ReActLoop
from pirn_agents.tool import Tool
from pirn_agents.types.agent_message import AgentMessage
from pirn_agents.types.agent_response import AgentResponse


class PlanReActPipeline(SubTapestry):
    """Plan with :class:`TaskPlanner`, then run a :class:`ReActLoop` per step."""

    def __init__(
        self,
        *,
        task: Knot | str,
        llm: Knot | LLMProvider,
        tools: Knot | Sequence[Tool] = (),
        max_iterations: Knot | int = 4,
        max_steps: Knot | int = 5,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            task=task,
            llm=llm,
            tools=tools,
            max_iterations=max_iterations,
            max_steps=max_steps,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        task: str,
        llm: LLMProvider,
        tools: Sequence[Tool] = (),
        max_iterations: int = 4,
        max_steps: int = 5,
        **_: Any,
    ) -> Any:
        """Plan then ReAct per step, surfacing a :class:`PlanReActResult`.

        Args:
            task: The goal to plan and execute.
            llm: Provider shared by the planner and every ReAct loop.
            tools: Tools available to each ReAct loop.
            max_iterations: Per-step ReAct iteration cap.
            max_steps: Cap on the number of plan steps executed.

        Returns:
            A terminal :class:`Source` whose output is the
            :class:`PlanReActResult`.

        Raises:
            TypeError: If ``llm``/``task`` have the wrong type.
            ValueError: If ``max_iterations`` or ``max_steps`` is not positive.
        """
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                f"PlanReActPipeline: llm must be an LLMProvider, got {type(llm).__name__}"
            )
        if not isinstance(task, str):
            raise TypeError(f"PlanReActPipeline: task must be a string, got {type(task).__name__}")
        if not isinstance(max_iterations, int) or max_iterations <= 0:
            raise ValueError(
                f"PlanReActPipeline: max_iterations must be positive, got {max_iterations!r}"
            )
        if not isinstance(max_steps, int) or max_steps <= 0:
            raise ValueError(f"PlanReActPipeline: max_steps must be positive, got {max_steps!r}")
        tool_tuple = tuple(tools)

        with Tapestry():
            planner = TaskPlanner(goal=task, llm=llm, _config=KnotConfig(id="pr_plan"))
        plan = await planner.process(goal=task, llm=llm)
        steps = tuple(plan.steps[:max_steps]) or (task,)

        step_responses: list[AgentResponse] = []
        for index, step in enumerate(steps):
            with Tapestry() as step_inner:
                loop = ReActLoop(
                    messages=(AgentMessage(role="user", content=step),),
                    llm=llm,
                    tools=tool_tuple,
                    max_iterations=max_iterations,
                    _config=KnotConfig(id=f"pr_react_{index}"),
                )
            run_result = await self._run_inner(step_inner)
            response = run_result.outputs[loop.knot_id]
            if isinstance(response, AgentResponse):
                step_responses.append(response)
            else:
                step_responses.append(AgentResponse(content=str(response)))

        final = step_responses[-1] if step_responses else AgentResponse(content="")
        result = PlanReActResult(
            plan=steps,
            step_responses=tuple(step_responses),
            final=final,
        )
        _result = result

        class _PlanReActResultSource(Source):
            async def process(self, **_: Any) -> PlanReActResult:
                return _result

        return _PlanReActResultSource(_config=KnotConfig(id="plan_react_result"))
