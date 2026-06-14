"""``ReActStepExecutor`` — single iteration of a ReAct reason+act loop.

One step = one LLM "thought" turn that may decide to call a tool, plus
the resulting observation. The output is the new tail of messages that
should be appended to the agent transcript: the assistant thought, the
optional tool-call surrogate, and the resulting tool observation.

The step is intentionally small and self-contained so that
:class:`ReActLoop` can compose any number of them inside an unrolled
inner :class:`Tapestry`. The :class:`ReActTerminationCheck` controls
early exit by inspecting the trailing assistant message.

Tool dispatch is name-keyed: the LLM is expected to emit a thought of
the form::

    Action: <tool_name>
    Action Input: <free-form input>

If a matching tool is registered, we invoke it; otherwise the
observation is a structured error string. A "Final Answer:" prefix
short-circuits tool selection: no tool call is performed and the
trailing assistant message stands as the final answer for the loop.

Algorithm:
    1. Receive ``context``, ``llm``, and ``tools`` at process time.
    2. Validate ``llm`` and each entry in ``tools``; raise on bad types.
    3. Build a tool registry keyed by ``tool.name``.
    4. Render the prompt from ``context``.
    5. Call ``llm.chat`` with the rendered prompt.
    6. Extract the thought text from the raw LLM response.
    7. If the thought contains ``"Final Answer:"``, return ``(thought,)``.
    8. Parse ``Action:`` / ``Action Input:`` lines from the thought.
    9. If no action name is found, return ``(thought,)``.
    10. Invoke the named tool (or produce an error observation).
    11. Return ``(thought, tool_call_message, observation)``.


References:
    - Yao et al. (2023) "ReAct: Synergizing Reasoning and Acting in Language Models"
      https://arxiv.org/abs/2210.03629
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.providers.llm_provider import LLMProvider
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
        llm: Knot | LLMProvider,
        tools: Knot | Sequence[Tool],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(context=context, llm=llm, tools=tools, _config=_config, **kwargs)

    async def process(
        self,
        context: Any,
        llm: LLMProvider,
        tools: Sequence[Tool],
        **_: Any,
    ) -> tuple[AgentMessage, ...]:
        """Emit a thought, optionally invoke a tool, and return the new tail of messages.

        Args:
            context: The current agent context used to render the prompt for the LLM.
            llm: The LLM provider used to generate the thought.
            tools: The sequence of available tools for this step.

        Returns:
            A tuple of new AgentMessage instances: the thought, optional tool-call surrogate,
            and observation; or just the thought when a Final Answer is emitted.

        Raises:
            TypeError: If llm is not an LLMProvider or any tool is not a Tool.
        """
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                f"ReActStepExecutor: llm must be an LLMProvider, got {type(llm).__name__}"
            )
        tool_tuple = tuple(tools)
        for index, candidate in enumerate(tool_tuple):
            if not isinstance(candidate, Tool):
                raise TypeError(
                    f"ReActStepExecutor: tools[{index}] must be a Tool, "
                    f"got {type(candidate).__name__}"
                )
        tools_by_name = {tool.name: tool for tool in tool_tuple}
        prompt = self._render_prompt(context, tool_tuple)
        chat_messages = [{"role": "user", "content": prompt}]
        raw = await llm.chat(chat_messages)
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
        observation_text = await self._invoke_tool(tools_by_name, action_name, action_input)
        observation = AgentMessage(
            role="tool",
            content=observation_text,
            tool_call_id=call_id,
            name=action_name,
        )
        return (thought, tool_call_message, observation)

    def _render_prompt(self, context: Any, tools: tuple[Tool, ...]) -> str:
        messages: tuple[AgentMessage, ...]
        if hasattr(context, "messages"):
            messages = tuple(context.messages)
        else:
            messages = tuple(context) if context else ()
        rendered = "\n".join(f"{m.role}: {m.content}" for m in messages)
        tool_lines = "\n".join(f"- {tool.name}: {tool.description}" for tool in tools)
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
                action_name = line[len(self._action_marker) :].strip() or None
            elif line.startswith(self._action_input_marker):
                action_input = line[len(self._action_input_marker) :].strip()
        return action_name, action_input

    @staticmethod
    async def _invoke_tool(tools_by_name: dict[str, Tool], name: str, raw_input: str) -> str:
        tool = tools_by_name.get(name)
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
