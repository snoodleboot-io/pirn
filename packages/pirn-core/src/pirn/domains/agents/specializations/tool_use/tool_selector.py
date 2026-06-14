"""``ToolSelector`` — LLM-driven tool selection from a list of available tools.

Given a user message and a list of :class:`Tool` instances, calls the LLM
to select the most appropriate tool(s) and returns a list of selected tool
names.

Algorithm:
    1. Receive resolved ``message``, ``tools``, and ``llm`` at process time.
    2. Validate ``llm`` is an :class:`LLMProvider`.
    3. Validate each entry in ``tools`` is a :class:`Tool`; reject empty sequence.
    4. Validate ``message`` is a string.
    5. Build a prompt listing available tool names and descriptions.
    6. Call ``llm.chat`` with the prompt.
    7. Extract text from the raw LLM response.
    8. If the response is empty or ``"NONE"``, return an empty list.
    9. Split response by line; keep only names present in the valid tool set.
    10. Return the filtered list of selected tool names.


References:
    - pirn-native design; no external references.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.providers.llm_provider import LLMProvider
from pirn.domains.agents.tool import Tool


class ToolSelector(Knot):
    """Call the LLM to select appropriate tools for a user message."""

    def __init__(
        self,
        *,
        message: Knot | str,
        tools: Knot | Sequence[Tool],
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(message=message, tools=tools, llm=llm, _config=_config, **kwargs)

    async def process(
        self,
        message: str,
        tools: Sequence[Tool],
        llm: LLMProvider,
        **_: Any,
    ) -> list[str]:
        """Ask the LLM which tools are appropriate for the message and return their names.

        Args:
            message: The user message string describing the task.
            tools: The sequence of available Tool instances.
            llm: The LLM provider used to perform tool selection.

        Returns:
            A list of tool name strings selected by the LLM.

        Raises:
            TypeError: If llm is not an LLMProvider, any tool is not a Tool, or
                message is not a string.
            ValueError: If tools is empty.
        """
        if not isinstance(llm, LLMProvider):
            raise TypeError(f"ToolSelector: llm must be an LLMProvider, got {type(llm).__name__}")
        tool_list = list(tools)
        for index, tool in enumerate(tool_list):
            if not isinstance(tool, Tool):
                raise TypeError(
                    f"ToolSelector: tools[{index}] must be a Tool, got {type(tool).__name__}"
                )
        if not tool_list:
            raise ValueError("ToolSelector: tools must not be empty")
        if not isinstance(message, str):
            raise TypeError(f"ToolSelector: message must be a string, got {type(message).__name__}")
        tool_descriptions = "\n".join(f"- {tool.name}: {tool.description}" for tool in tool_list)
        available_names = ", ".join(tool.name for tool in tool_list)
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
        raw = await llm.chat([{"role": "user", "content": prompt}])
        text = self._extract_text(raw).strip()
        if not text or text.upper() == "NONE":
            return []
        valid_names = {tool.name for tool in tool_list}
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
