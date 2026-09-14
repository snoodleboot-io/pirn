"""``ToolRouter`` — pick a tool capability for a single plan step.

Algorithm:
    1. Receive the resolved ``step`` string and ``tools`` sequence (each
       validated into a :class:`ToolFactory`).
    2. Validate input types at process time.
    3. Lower-case the step text.
    4. Iterate tools; return a ``ToolCall`` for the first whose name appears as a substring.
    5. Raise ``ValueError`` if no tool name matches the step.


References:
    - :class:`pirn_agents.tools.tool_factory.ToolFactory`
    - :class:`pirn_agents.tools.tool_call.ToolCall`
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.interfaces.router import Router
from pirn_agents.tools.tool_call import ToolCall
from pirn_agents.tools.tool_factory import ToolFactory


class ToolRouter(Router):
    """Routes a single plan step to one of the registered tool capabilities.

    A tool is selected when its ``name`` (case-insensitive) appears as
    a substring of the step. The first matching tool wins; if no tool
    matches a ``ValueError`` is raised — the planner is expected to
    produce steps addressable by the available tool registry.
    """

    def __init__(
        self,
        *,
        step: Knot | str,
        tools: Knot | Sequence[Any],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            step=step,
            tools=tools,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        step: str,
        tools: Sequence[ToolFactory],
        **_: Any,
    ) -> ToolCall:
        """Match the plan step to a registered tool and return the corresponding ToolCall.

        Args:
            step: The plan step text to match against registered tool names.
            tools: The registered capabilities to search by name substring.

        Returns:
            A ToolCall targeting the first tool whose name appears in the step.

        Raises:
            TypeError: If tools contains something that is not a tool capability.
            ValueError: If step is empty, tools is empty, or no tool name appears in the step.
        """
        if not isinstance(tools, Sequence) or isinstance(tools, (str, bytes)):
            raise TypeError("ToolRouter: tools must be a sequence of tool capabilities")
        if not tools:
            raise ValueError("ToolRouter: tools must be non-empty")
        factories = [ToolFactory.of(tool) for tool in tools]
        if not isinstance(step, str) or not step:
            raise ValueError(f"ToolRouter: step must be a non-empty string, got {step!r}")
        step_lower = step.lower()
        for factory in factories:
            if factory.name.lower() in step_lower:
                return ToolCall(
                    tool_name=factory.name,
                    arguments={"step": step},
                    call_id=f"call-{uuid.uuid4().hex[:12]}",
                )
        raise ValueError(
            f"ToolRouter: step {step!r} does not reference any registered "
            f"tool {[factory.name for factory in factories]!r}"
        )
