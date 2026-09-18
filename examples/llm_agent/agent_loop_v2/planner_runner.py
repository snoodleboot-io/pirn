"""``PlannerRunner`` — the Planner → ToolRouter → ToolExecutor inner pipeline.

Part of the ``examples.llm_agent.agent_loop_v2`` example.
"""

from __future__ import annotations

from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.nodes.sub_tapestry import SubTapestry
from pirn_agents.input.context_builder import ContextBuilder
from pirn_agents.planning.planner import Planner
from pirn_agents.planning.tool_executor import ToolExecutor
from pirn_agents.planning.tool_router import ToolRouter

from examples.llm_agent.agent_loop_v2.plan_first_step import _PlanFirstStep
from examples.llm_agent.agent_loop_v2.planned_action import PlannedAction
from examples.llm_agent.agent_loop_v2.session_context import SessionContext
from examples.llm_agent.agent_loop_v2.stub_toolbox import StubToolbox
from examples.llm_agent.agent_loop_v2.tool_result_wrapper import _ToolResultWrapper


class PlannerRunner(SubTapestry):
    """ContextBuilder → Planner → PlanFirstStep → ToolRouter → ToolExecutor.

    ``StubToolbox.planner_llm`` is scripted to emit steps containing tool names so
    ``ToolRouter`` can match them.  ``_PlanFirstStep`` extracts the first
    step string from the ``Plan`` before passing it to ``ToolRouter``.
    """

    _system_prompt: ClassVar[str] = (
        "You are a planning assistant. Produce a numbered list of steps. "
        "Each step must start with a tool name (search, calculate, or lookup) "
        "followed by a colon and a description. One step per line."
    )

    async def process(self, ctx: SessionContext, action: PlannedAction, **_: Any) -> Knot:
        msgs = ctx.seed_messages(self._system_prompt)
        msgs_param = Parameter(
            "messages",
            tuple,
            default=msgs,
            _config=KnotConfig(id="msgs"),
        )
        context_k = ContextBuilder(messages=msgs_param, _config=KnotConfig(id="ctx"))
        plan_k = Planner(
            context=context_k, llm=StubToolbox.planner_llm, _config=KnotConfig(id="plan")
        )
        step_k = _PlanFirstStep(plan=plan_k, _config=KnotConfig(id="step"))
        router_k = ToolRouter(
            step=step_k,
            tools=list(StubToolbox.all_tools),
            _config=KnotConfig(id="route"),
        )
        exec_k = ToolExecutor(
            call=router_k,
            tools=list(StubToolbox.all_tools),
            _config=KnotConfig(id="exec"),
        )
        return _ToolResultWrapper(exec_out=exec_k, _config=KnotConfig(id="out"))
