"""``ToolRouter`` — pick a :class:`Tool` for a single plan step."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.tool import Tool
from pirn.domains.agents.types.tool_call import ToolCall


class ToolRouter(Knot):
    """Routes a single plan step to one of the registered :class:`Tool`s.

    A tool is selected when its ``name`` (case-insensitive) appears as
    a substring of the step. The first matching tool wins; if no tool
    matches a ``ValueError`` is raised — the planner is expected to
    produce steps addressable by the available tool registry.
    """

    def __init__(
        self,
        *,
        step: Knot | str,
        tools: Sequence[Tool],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(tools, Sequence) or isinstance(tools, (str, bytes)):
            raise TypeError(
                "ToolRouter: tools must be a sequence of Tool instances"
            )
        if not tools:
            raise ValueError("ToolRouter: tools must be non-empty")
        for index, tool in enumerate(tools):
            if not isinstance(tool, Tool):
                raise TypeError(
                    f"ToolRouter: tools[{index}] must be a Tool, "
                    f"got {type(tool).__name__}"
                )
        super().__init__(
            step=step,
            tools=tuple(tools),
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        step: str,
        tools: tuple[Tool, ...],
        **_: Any,
    ) -> ToolCall:
        """Match the plan step to a registered tool and return the corresponding ToolCall.

        Args:
            step: The plan step text to match against registered tool names.
            tools: The registered tools to search by name substring.

        Returns:
            A ToolCall targeting the first tool whose name appears in the step.

        Raises:
            ValueError: If step is empty or no registered tool name appears in the step.
        """
        if not isinstance(step, str) or not step:
            raise ValueError(
                "ToolRouter: step must be a non-empty string, "
                f"got {step!r}"
            )
        step_lower = step.lower()
        for tool in tools:
            if tool.name.lower() in step_lower:
                return ToolCall(
                    tool_name=tool.name,
                    arguments={"step": step},
                    call_id=f"call-{uuid.uuid4().hex[:12]}",
                )
        raise ValueError(
            f"ToolRouter: step {step!r} does not reference any registered "
            f"tool {[tool.name for tool in tools]!r}"
        )
