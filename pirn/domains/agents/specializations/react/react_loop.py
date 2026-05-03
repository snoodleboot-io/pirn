"""``ReActLoop`` — composed reason+act agent loop.

A :class:`SubTapestry` that wires:

1. :class:`ContextBuilder` over the input messages.
2. A fixed-length unrolled chain of :class:`ReActStepExecutor` instances,
   each guarded by :class:`ReActTerminationCheck`. Once termination fires
   (final-answer marker emitted, or iteration cap reached), subsequent
   steps short-circuit and propagate the prior message tail unchanged.
3. A final :class:`ReActResponseExtractor` knot that converts the
   accumulated messages into an :class:`AgentResponse`.

A fixed-iteration unrolled SubTapestry is used in place of dynamic
loops: each step sits behind its own :class:`ReActTerminationCheck`, so
runs that complete early simply pay the cost of a few short-circuit
knots after the final answer is found. ``max_iterations`` caps the
number of step knots the inner tapestry contains.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.input.context_builder import ContextBuilder
from pirn.domains.agents.llm_provider import LLMProvider
from pirn.domains.agents.tool import Tool
from pirn.domains.agents.specializations.react.messages_passthrough import (
    MessagesPassthrough,
)
from pirn.domains.agents.specializations.react.react_response_extractor import (
    ReActResponseExtractor,
)
from pirn.domains.agents.specializations.react.react_step_accumulator import (
    ReActStepAccumulator,
)
from pirn.domains.agents.specializations.react.react_step_executor import (
    ReActStepExecutor,
)
from pirn.domains.agents.specializations.react.react_termination_check import (
    ReActTerminationCheck,
)
from pirn.domains.agents.types.agent_message import AgentMessage
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class ReActLoop(SubTapestry):
    """Composed ReAct loop returning an :class:`AgentResponse`."""

    def __init__(
        self,
        *,
        messages: Knot | tuple[AgentMessage, ...] | list[AgentMessage],
        llm: LLMProvider,
        tools: Sequence[Tool],
        _config: KnotConfig,
        max_iterations: int = 10,
        **kwargs: Any,
    ) -> None:
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                "ReActLoop: llm must be an LLMProvider, "
                f"got {type(llm).__name__}"
            )
        if not isinstance(max_iterations, int) or max_iterations <= 0:
            raise ValueError(
                "ReActLoop: max_iterations must be a positive int, "
                f"got {max_iterations!r}"
            )
        tool_tuple = tuple(tools)
        for index, candidate in enumerate(tool_tuple):
            if not isinstance(candidate, Tool):
                raise TypeError(
                    f"ReActLoop: tools[{index}] must be a Tool, "
                    f"got {type(candidate).__name__}"
                )
        self._llm = llm
        self._tools = tool_tuple
        self._max_iterations = max_iterations
        super().__init__(messages=messages, _config=_config, **kwargs)

    async def process(
        self,
        messages: tuple[AgentMessage, ...] | list[AgentMessage],
        **_: Any,
    ) -> AgentResponse:
        """Run the unrolled ReAct loop over the seed messages and return the final AgentResponse.

        Args:
            messages: The seed conversation messages to initialize the ReAct loop context.

        Returns:
            An AgentResponse extracted from the final accumulated message transcript.
        """
        seed_messages = tuple(messages)
        with Tapestry() as inner:
            seed = MessagesPassthrough(
                messages=seed_messages,
                _config=KnotConfig(id="seed"),
            )
            ContextBuilder(
                messages=seed,
                _config=KnotConfig(id="initial_context"),
            )
            running_messages: Knot = seed
            already_terminated: Knot | bool = False
            for index in range(self._max_iterations):
                context_knot = ContextBuilder(
                    messages=running_messages,
                    _config=KnotConfig(id=f"context_{index}"),
                )
                step = ReActStepExecutor(
                    context=context_knot,
                    llm=self._llm,
                    tools=self._tools,
                    _config=KnotConfig(id=f"step_{index}"),
                )
                running_messages = ReActStepAccumulator(
                    prior=running_messages,
                    step_output=step,
                    already_terminated=already_terminated,
                    _config=KnotConfig(id=f"accum_{index}"),
                )
                already_terminated = ReActTerminationCheck(
                    latest_response=step,
                    max_iterations=self._max_iterations,
                    current_iteration=index + 1,
                    _config=KnotConfig(id=f"gate_{index}"),
                )
            ReActResponseExtractor(
                messages=running_messages,
                _config=KnotConfig(id="response"),
            )
        inner_result = await self._run_inner(inner)
        response = inner_result.outputs.get("response")
        if not isinstance(response, AgentResponse):
            return AgentResponse(content="", finish_reason="length")
        return response
