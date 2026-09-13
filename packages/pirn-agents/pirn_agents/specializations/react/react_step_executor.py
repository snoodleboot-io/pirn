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

If a matching tool is registered, we invoke it — through the engine, as a
:class:`~pirn_agents.tools.tool_invocation.ToolInvocation` (PIR-856), the
same knot :class:`~pirn_agents.planning.tool_executor.ToolExecutor` and
:class:`~pirn_agents.agent.parallel_tool_executor.ParallelToolExecutor` use,
so the call gets its own lineage/history/``Ok|Err|Skipped`` instead of being
awaited inline. Otherwise the observation is a structured error string built
directly, with nothing to invoke. A "Final Answer:" prefix short-circuits
tool selection: no tool call is performed and the trailing assistant message
stands as the final answer for the loop.

This is a :class:`~pirn_agents.specializations.base.agent_pipeline.AgentPipeline`
(the ``specializations/**`` ``SubTapestry`` seam) rather than a plain
``Knot``: the thought/prompt/parsing logic is ordinary Python decision-making
that runs before any graph is built — exactly like
:class:`~pirn_agents.planning.tool_executor.ToolExecutor` deciding which tool
a call names — but the tool call itself must be a node in an inner pipeline,
whose sink ``process()`` returns.

Algorithm:
    1. Receive ``context``, ``llm``, ``tools``, and ``already_terminated``
       at process time.
    2. Validate ``llm`` and each entry in ``tools``; raise on bad types.
    3. If ``already_terminated`` is true, return a terminal producing ``()``
       — an earlier step has produced the final answer and this unrolled
       step is a no-op.
    4. Build a tool registry keyed by ``tool.name``.
    5. Render the prompt from ``context``.
    6. Call ``llm.chat`` with the rendered prompt.
    7. Extract the thought text from the raw LLM response.
    8. If the thought contains ``"Final Answer:"``, return a terminal
       producing ``(thought,)``.
    9. Parse ``Action:`` / ``Action Input:`` lines from the thought.
    10. If no action name is found, return a terminal producing ``(thought,)``.
    11. If the named tool is not registered, return a terminal producing the
        three messages directly — there is nothing to invoke.
    12. Otherwise wire a ``ToolInvocation`` for the named tool and return the
        assembler knot that turns its ``ToolResult`` into the three messages.


References:
    - Yao et al. (2023) "ReAct: Synergizing Reasoning and Acting in Language Models"
      https://arxiv.org/abs/2210.03629
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.prompt.prompt_binding import PromptBinding
from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.tools.tool import Tool
from pirn_agents.tools.tool_call import ToolCall
from pirn_agents.tools.tool_invocation import ToolInvocation
from pirn_agents.tools.tool_result import ToolResult
from pirn_agents.tools.tool_status import ToolStatus
from pirn_agents.types.messaging.agent_message import AgentMessage


@knot
async def _constant_messages(value: tuple[AgentMessage, ...]) -> tuple[AgentMessage, ...]:
    """Terminal for a branch that needs no tool call: the value is already final.

    A knot rather than a plain early return: ``process()`` must return the
    sink of an inner pipeline now, so every branch — including the ones with
    nothing left to compute — needs a graph node to return.
    """
    return value


@knot
async def _observation_assembler(
    thought: AgentMessage,
    tool_call_message: AgentMessage,
    call_id: str,
    action_name: str,
    tool_result: ToolResult,
) -> tuple[AgentMessage, ...]:
    """Terminal: turn a completed ``ToolInvocation``'s result into the step's messages."""
    content = (
        str(tool_result.result)
        if tool_result.status is ToolStatus.OK
        else (tool_result.error or f"Tool {action_name!r} failed with no message.")
    )
    observation = AgentMessage(role="tool", content=content, tool_call_id=call_id, name=action_name)
    return (thought, tool_call_message, observation)


class ReActStepExecutor(AgentPipeline):
    """One ReAct iteration: thought → optional tool-call → observation."""

    _react_prompt: ClassVar[PromptBinding] = PromptBinding(
        name="specializations.react.react_step_executor.react_prompt",
        default=(
            "You are a ReAct agent. Available tools:\n"
            "{{ tools }}\n\n"
            "Conversation so far:\n"
            "{{ conversation }}\n\n"
            "Reason step-by-step. To act, emit:\n"
            "Action: <tool_name>\nAction Input: <input>\n"
            "Otherwise emit a Final Answer."
        ),
    )

    _final_answer_marker: str = "Final Answer:"
    _action_marker: str = "Action:"
    _action_input_marker: str = "Action Input:"

    def __init__(
        self,
        *,
        context: Knot,
        llm: Knot | LLMProvider,
        tools: Knot | Sequence[Tool],
        already_terminated: Knot | bool,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            context=context,
            llm=llm,
            tools=tools,
            already_terminated=already_terminated,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        context: Any,
        llm: LLMProvider,
        tools: Sequence[Tool],
        already_terminated: bool,
        **_: Any,
    ) -> Knot:
        """Emit a thought, optionally wire a tool call, and return the step's sink knot.

        Args:
            context: The current agent context used to render the prompt for the LLM.
            llm: The LLM provider used to generate the thought.
            tools: The sequence of available tools for this step.
            already_terminated: Whether an earlier step has already signalled termination.
                When true this step is a no-op and no LLM call is made.

        Returns:
            The sink of the inner pipeline. Its output — a tuple of new
            ``AgentMessage`` instances: the thought, optional tool-call
            surrogate, and observation (or just the thought for a Final
            Answer or no-action turn; empty when already terminated) —
            becomes this knot's output.

        Raises:
            TypeError: If llm is not an LLMProvider or any tool is not a Tool.
        """
        tool_tuple = tuple(tools)
        for index, candidate in enumerate(tool_tuple):
            if not isinstance(candidate, Tool):
                raise TypeError(
                    f"ReActStepExecutor: tools[{index}] must be a Tool, "
                    f"got {type(candidate).__name__}"
                )
        if already_terminated:
            return _constant_messages(value=(), _config=KnotConfig(id="noop"))
        tools_by_name = {tool.name: tool for tool in tool_tuple}
        prompt = self._render_prompt(context, tool_tuple)
        chat_messages = [{"role": "user", "content": prompt}]
        raw = await llm.chat(chat_messages)
        thought_text = self._extract_text(raw)
        thought = AgentMessage(role="assistant", content=thought_text)
        if self._final_answer_marker in thought_text:
            return _constant_messages(value=(thought,), _config=KnotConfig(id="final-answer"))
        action_name, action_input = self._parse_action(thought_text)
        if action_name is None:
            return _constant_messages(value=(thought,), _config=KnotConfig(id="no-action"))
        call_id = f"{self.knot_id}-call"
        tool_call_message = AgentMessage(
            role="assistant",
            content=f"Calling tool {action_name} with: {action_input}",
            tool_call_id=call_id,
            name=action_name,
        )
        tool = tools_by_name.get(action_name)
        if tool is None:
            observation = AgentMessage(
                role="tool",
                content=f"Tool {action_name!r} is not registered.",
                tool_call_id=call_id,
                name=action_name,
            )
            return _constant_messages(
                value=(thought, tool_call_message, observation),
                _config=KnotConfig(id="tool-not-registered"),
            )
        call = ToolCall(tool_name=action_name, arguments={"input": action_input}, call_id=call_id)
        invocation = ToolInvocation(tool=tool, call=call, _config=KnotConfig(id="tool-call"))
        return _observation_assembler(
            thought=thought,
            tool_call_message=tool_call_message,
            call_id=call_id,
            action_name=action_name,
            tool_result=invocation,
            _config=KnotConfig(id="assemble"),
        )

    def _render_prompt(self, context: Any, tools: tuple[Tool, ...]) -> str:
        messages: tuple[AgentMessage, ...]
        if hasattr(context, "messages"):
            messages = tuple(context.messages)
        else:
            messages = tuple(context) if context else ()
        rendered = "\n".join(f"{m.role}: {m.content}" for m in messages)
        tool_lines = "\n".join(f"- {tool.name}: {tool.description}" for tool in tools)
        return type(self)._react_prompt.render(
            {"tools": tool_lines, "conversation": rendered},
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
