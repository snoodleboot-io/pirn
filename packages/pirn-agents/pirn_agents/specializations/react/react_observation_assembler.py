"""``ReActObservationAssembler`` — turn a ReAct tool call's ``Result`` into messages.

Internal knot for
:class:`~pirn_agents.specializations.react.react_step_executor.ReActStepExecutor`.
Wired with ``error_policy=RECEIVE_ERRORS`` over the step's tool-call knot, so
``outcome`` here is the call's raw ``Ok``/``Err``/``Skipped``; the
:class:`~pirn_agents.tools.tool_result.ToolResult` view renders it into the
observation message's content.

Before PIR-873 this was a module-level ``@KnotFactory.knot`` coroutine. That
decorator builds a ``Knot`` subclass dynamically from a function, which is the
right tool for a test double or a caller-supplied capability but not for a
knot that ships in the package: the class has no module of its own, so it
cannot be imported, subclassed, documented or found by the registry's
uniqueness checks under a name anyone can spell — and a module-level function
is forbidden outright by the Python conventions.

Algorithm:
    1. Build a :class:`ToolResult` view over the call's ``Result``.
    2. Take its rendered value as the observation's content, or its error
       message when the call failed (falling back to a message naming the tool
       when the failure carried none).
    3. Return ``(thought, tool_call_message, observation)`` — the step's new
       message tail.

Internal API.
"""

from __future__ import annotations

from typing import Any

from pirn.core.err import Err
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.ok import Ok
from pirn.core.skipped import Skipped

from pirn_agents.tools.tool_result import ToolResult
from pirn_agents.types.messaging.agent_message import AgentMessage


class ReActObservationAssembler(Knot):
    """Assemble one ReAct step's thought, tool-call surrogate and observation."""

    def __init__(
        self,
        *,
        thought: Knot | AgentMessage,
        tool_call_message: Knot | AgentMessage,
        call_id: Knot | str,
        action_name: Knot | str,
        outcome: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            thought=thought,
            tool_call_message=tool_call_message,
            call_id=call_id,
            action_name=action_name,
            outcome=outcome,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        thought: AgentMessage,
        tool_call_message: AgentMessage,
        call_id: str,
        action_name: str,
        outcome: Ok[Any] | Err | Skipped,
        **_: Any,
    ) -> tuple[AgentMessage, ...]:
        """Render the call's outcome as this step's message tail.

        Args:
            thought: The assistant message the step's LLM turn produced.
            tool_call_message: The assistant surrogate naming the call.
            call_id: The call's id, carried on the observation message.
            action_name: The tool the step selected.
            outcome: The tool call's ``Result``.

        Returns:
            The thought, the tool-call surrogate and the observation, in order.
        """
        view = ToolResult.from_result(call_id, outcome)
        content = (
            str(view.result)
            if view.error is None
            else (view.error or f"Tool {action_name!r} failed with no message.")
        )
        observation = AgentMessage(
            role="tool", content=content, tool_call_id=call_id, name=action_name
        )
        return (thought, tool_call_message, observation)
