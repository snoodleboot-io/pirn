"""``ReActStepExecutor`` — single iteration of a ReAct reason+act loop.

One step = one LLM "thought" turn that may decide to call a tool, plus
the resulting observation. The output is the new tail of messages that
should be appended to the agent transcript: the assistant thought, the
optional tool-call surrogate, and the resulting tool observation.

The step is intentionally small and self-contained so that
:class:`ReActLoop` can compose any number of them inside an unrolled
inner :class:`Tapestry`. The :class:`ReActTerminationGate` controls
early exit by inspecting the trailing assistant message.

Tool dispatch is name-keyed: the LLM is expected to emit a thought of
the form::

    Action: <tool_name>
    Action Input: <free-form input>

If a matching tool is registered, we invoke it; otherwise the
observation is a structured error string. A "Final Answer:" prefix
short-circuits tool selection: no tool call is performed and the
trailing assistant message stands as the final answer for the loop.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider
from pirn.domains.agents.tool import Tool
from pirn.domains.agents.types.agent_message import AgentMessage


class ReActStepExecutor(Knot):
    """One ReAct iteration: thought → optional tool-call → observation."""

    _final_answer_marker: str = "Final Answer:"
    _action_marker: str = "Action:"
    _action_input_marker: str = "Action Input:"

    def __init__(
        self,
        *,
        context: Knot,
        llm: LLMProvider,
        tools: Sequence[Tool],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                "ReActStepExecutor: llm must be an LLMProvider, "
                f"got {type(llm).__name__}"
            )
        tool_tuple = tuple(tools)
        for index, candidate in enumerate(tool_tuple):
            if not isinstance(candidate, Tool):
                raise TypeError(
                    f"ReActStepExecutor: tools[{index}] must be a Tool, "
                    f"got {type(candidate).__name__}"
                )
        self._llm = llm
        self._tools = tool_tuple
        self._tools_by_name = {tool.name: tool for tool in tool_tuple}
        super().__init__(context=context, _config=_config, **kwargs)

    async def process(
        self,
        context: Any,
        **_: Any,
    ) -> tuple[AgentMessage, ...]:
        prompt = self._render_prompt(context)
        chat_messages = [{"role": "user", "content": prompt}]
        raw = await self._llm.chat(chat_messages)
        thought_text = self._extract_text(raw)
        thought = AgentMessage(role="assistant", content=thought_text)
        if self._final_answer_marker in thought_text:
            return (thought,)
        action_name, action_input = self._parse_action(thought_text)
        if action_name is None:
            return (thought,)
        call_id = f"{self.knot_id}-call"
        tool_call_message = AgentMessage(
            role="assistant",
            content=f"Calling tool {action_name} with: {action_input}",
            tool_call_id=call_id,
            name=action_name,
        )
        observation_text = await self._invoke_tool(action_name, action_input)
        observation = AgentMessage(
            role="tool",
            content=observation_text,
            tool_call_id=call_id,
            name=action_name,
        )
        return (thought, tool_call_message, observation)

    def _render_prompt(self, context: Any) -> str:
        messages: tuple[AgentMessage, ...]
        if hasattr(context, "messages"):
            messages = tuple(context.messages)
        else:
            messages = tuple(context) if context else ()
        rendered = "\n".join(f"{m.role}: {m.content}" for m in messages)
        tool_lines = "\n".join(
            f"- {tool.name}: {tool.description}" for tool in self._tools
        )
        return (
            "You are a ReAct agent. Available tools:\n"
            f"{tool_lines}\n\n"
            "Conversation so far:\n"
            f"{rendered}\n\n"
            "Reason step-by-step. To act, emit:\n"
            "Action: <tool_name>\nAction Input: <input>\n"
            "Otherwise emit a Final Answer."
        )

    def _parse_action(self, text: str) -> tuple[str | None, str]:
        action_name: str | None = None
        action_input = ""
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if line.startswith(self._action_marker) and not line.startswith(
                self._action_input_marker
            ):
                action_name = line[len(self._action_marker):].strip() or None
            elif line.startswith(self._action_input_marker):
                action_input = line[len(self._action_input_marker):].strip()
        return action_name, action_input

    async def _invoke_tool(self, name: str, raw_input: str) -> str:
        tool = self._tools_by_name.get(name)
        if tool is None:
            return f"Tool {name!r} is not registered."
        try:
            result = await tool.invoke({"input": raw_input})
        except Exception as exc:
            return f"Tool {name!r} raised: {exc}"
        return str(result)

    @staticmethod
    def _extract_text(raw: Any) -> str:
        if isinstance(raw, str):
            return raw
        if isinstance(raw, dict):
            content = raw.get("content")
            if isinstance(content, str):
                return content
            if isinstance(content, list) and content:
                first = content[0]
                if isinstance(first, dict):
                    text = first.get("text")
                    if isinstance(text, str):
                        return text
                if isinstance(first, str):
                    return first
            text = raw.get("text")
            if isinstance(text, str):
                return text
        return str(raw)
