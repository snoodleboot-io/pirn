"""``LLMTaskRunner`` — the ContextBuilder → LLMCall → OutputParser inner pipeline.

Part of the ``examples.llm_agent.agent_loop_v2`` example.
"""

from __future__ import annotations

from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.nodes.sub_tapestry import SubTapestry
from pirn_agents.generation.llm_call import LLMCall
from pirn_agents.generation.output_parser import OutputParser
from pirn_agents.input.context_builder import ContextBuilder

from examples.llm_agent.agent_loop_v2.planned_action import PlannedAction
from examples.llm_agent.agent_loop_v2.session_context import SessionContext
from examples.llm_agent.agent_loop_v2.stub_toolbox import StubToolbox


class LLMTaskRunner(SubTapestry):
    """ContextBuilder → LLMCall → OutputParser inner pipeline."""

    _system_prompt: ClassVar[str] = (
        "You are a helpful assistant. Answer the user's question clearly and concisely."
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
        llm_k = LLMCall(context=context_k, llm=StubToolbox.llm, _config=KnotConfig(id="call"))
        return OutputParser(response=llm_k, _config=KnotConfig(id="out"))
