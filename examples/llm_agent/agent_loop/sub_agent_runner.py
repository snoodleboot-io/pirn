"""``SubAgentRunner`` — runs a sub-agent action as its own inner tapestry.

Part of the ``examples.llm_agent.agent_loop`` example.
"""

from __future__ import annotations

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.nodes.sub_tapestry import SubTapestry

from examples.llm_agent.agent_loop.knots import execute_subagent, prepare_context
from examples.llm_agent.agent_loop.planned_action import PlannedAction
from examples.llm_agent.agent_loop.session_context import SessionContext


class SubAgentRunner(SubTapestry):
    """Run a sub-agent as its own inner tapestry (prepare_context → execute_subagent)."""

    async def process(self, action: PlannedAction, ctx: SessionContext, **_) -> Knot:
        context = action.args.get("context", ctx.current_message)

        raw_p = Parameter("raw", str, default=context, _config=KnotConfig(id="context_input"))
        ctx_knot = prepare_context(raw=raw_p, _config=KnotConfig(id="prepare"))
        sink = execute_subagent(
            prepared=ctx_knot,
            action=action,
            ctx=ctx,
            _config=KnotConfig(id="subagent_output"),
        )

        return sink
