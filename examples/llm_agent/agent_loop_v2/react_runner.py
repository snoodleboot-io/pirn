"""``ReActRunner`` — the ReActLoop inner pipeline (reason + act with stub tools).

Part of the ``examples.llm_agent.agent_loop_v2`` example.
"""

from __future__ import annotations

from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.sub_tapestry import SubTapestry
from pirn_agents.specializations.react.react_loop import ReActLoop

from examples.llm_agent.agent_loop_v2.planned_action import PlannedAction
from examples.llm_agent.agent_loop_v2.session_context import SessionContext
from examples.llm_agent.agent_loop_v2.stub_toolbox import StubToolbox


class ReActRunner(SubTapestry):
    """ReActLoop inner pipeline — reason + act with stub tools."""

    _system_prompt: ClassVar[str] = (
        "You are a research assistant. Use the search, calculate, or lookup tools "
        "as needed. When you have enough information emit: Final Answer: <text>"
    )
    _max_iterations: ClassVar[int] = 3

    async def process(self, ctx: SessionContext, action: PlannedAction, **_: Any) -> Knot:
        msgs = ctx.seed_messages(self._system_prompt)
        return ReActLoop(
            messages=list(msgs),
            llm=StubToolbox.llm,
            tools=list(StubToolbox.all_tools),
            max_iterations=self._max_iterations,
            _config=KnotConfig(id="react_loop"),
        )
