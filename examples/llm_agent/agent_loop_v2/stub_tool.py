"""``StubTool`` — a deterministic ``Tool`` knot that formats a bound template.

Part of the ``examples.llm_agent.agent_loop_v2`` example.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn_agents.tools.tool import Tool


class StubTool(Tool):
    """Deterministic tool knot that formats a bound template with the call's input.

    A tool is a ``Knot`` class (ADR "agents speaks core", WS1): ``input`` (the
    ReAct shape) or ``step`` (the plan-step shape ``ToolRouter`` emits) is the
    call argument and ``result_template`` is bound once per capability with
    :meth:`Tool.bind`; ``named()`` then gives each bound capability its own
    name and description for the model.
    """

    def __init__(
        self,
        *,
        input: Knot | str = "",
        step: Knot | str = "",
        result_template: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            input=input,
            step=step,
            result_template=result_template,
            _config=_config,
            **kwargs,
        )

    async def process(
        self, input: str = "", step: str = "", result_template: str = "", **_: Any
    ) -> str:
        return result_template.format(arg=input or step)
