"""``ToolSelector`` — LLM-driven tool selection from a list of available tools.

Given a user message and a list of :class:`Tool` instances, calls the LLM
to select the most appropriate tool(s) and returns a list of selected tool
names.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider
from pirn.domains.agents.tool import Tool


class ToolSelector(Knot):
    """Call the LLM to select appropriate tools for a user message."""

    def __init__(
        self,
        *,
        message: Knot | str,
        tools: Sequence[Tool],
        llm: LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                "ToolSelector: llm must be an LLMProvider, "
                f"got {type(llm).__name__}"
            )
        tool_list = list(tools)
        for index, tool in enumerate(tool_list):
            if not isinstance(tool, Tool):
                raise TypeError(
                    f"ToolSelector: tools[{index}] must be a Tool, "
                    f"got {type(tool).__name__}"
                )
        if not tool_list:
            raise ValueError("ToolSelector: tools must not be empty")
        self._llm = llm
        self._tools = tool_list
        super().__init__(message=message, _config=_config, **kwargs)

    async def process(self, message: str, **_: Any) -> list[str]:
        """Ask the LLM which tools are appropriate for the message and return their names.

        Args:
            message: The user message string describing the task.

        Returns:
            A list of tool name strings selected by the LLM.

        Raises:
            TypeError: If message is not a string.
        """
        if not isinstance(message, str):
            raise TypeError(
                "ToolSelector: message must be a string, "
                f"got {type(message).__name__}"
            )
        tool_descriptions = "\n".join(
            f"- {tool.name}: {tool.description}" for tool in self._tools
        )
        available_names = ", ".join(tool.name for tool in self._tools)
        prompt = (
            "Given the following user message and available tools, select "
            "the tool name(s) most appropriate for this task. "
            f"Available tools: {available_names}. "
            "Reply with only the tool name(s), one per line, using the "
            "exact names from the list. If no tool is appropriate, reply "
            "with NONE.\n\n"
            f"Tools:\n{tool_descriptions}\n\n"
            f"User message: {message}"
        )
        raw = await self._llm.chat([{"role": "user", "content": prompt}])
        text = self._extract_text(raw).strip()
        if not text or text.upper() == "NONE":
            return []
        valid_names = {tool.name for tool in self._tools}
        selected: list[str] = []
        for line in text.splitlines():
            name = line.strip()
            if name in valid_names:
                selected.append(name)
        return selected

    @staticmethod
    def _extract_text(raw: Any) -> str:
        if isinstance(raw, str):
            return raw
        if isinstance(raw, dict):
            content = raw.get("content")
            if isinstance(content, str):
                return content
        return str(raw)
