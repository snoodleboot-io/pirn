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

The termination signal is threaded into every downstream knot of the
next iteration — the step executor, the accumulator, and the next gate.
The step executor needs it to avoid paying for an LLM call whose result
would be discarded; the gate needs it because a step that runs after the
final answer emits no marker of its own, so without the latch the gate
would reopen and a later accumulator would append over the answer.

Algorithm:
    1. Receive ``messages``, ``llm``, ``tools``, and ``max_iterations``
       at process time.
    2. Validate input types; raise on bad types or non-positive iterations.
    3. Build an inner :class:`Tapestry` with a fixed-length unrolled chain:
       a. Seed knot: :class:`MessagesPassthrough` over the input messages.
       b. For each iteration index 0..max_iterations-1, threading the
          prior iteration's termination signal into all three knots:
          i.  :class:`ContextBuilder` over the running message tail.
          ii. :class:`ReActStepExecutor` with ``llm`` and ``tools``.
          iii. :class:`ReActStepAccumulator` appending the step output.
          iv. :class:`ReActTerminationCheck` gating further iterations.
       c. :class:`ReActResponseExtractor` over the final message tail.
    4. Run the inner tapestry via ``self._run_inner(inner)``.
    5. Extract the ``"response"`` output from the inner run result.
    6. Return the :class:`AgentResponse`, or a default empty response on
       failure.


References:
    - Yao et al. (2023) "ReAct: Synergizing Reasoning and Acting in Language Models"
      https://arxiv.org/abs/2210.03629
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.input.context_builder import ContextBuilder
from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.specializations.react.messages_passthrough import (
    MessagesPassthrough,
)
from pirn_agents.specializations.react.react_response_extractor import (
    ReActResponseExtractor,
)
from pirn_agents.specializations.react.react_step_accumulator import (
    ReActStepAccumulator,
)
from pirn_agents.specializations.react.react_step_executor import (
    ReActStepExecutor,
)
from pirn_agents.specializations.react.react_termination_check import (
    ReActTerminationCheck,
)
from pirn_agents.tools.tool import Tool
from pirn_agents.types.messaging.agent_message import AgentMessage


class ReActLoop(AgentPipeline):
    """Composed ReAct loop returning an :class:`AgentResponse`."""

    def __init__(
        self,
        *,
        messages: Knot | tuple[AgentMessage, ...] | list[AgentMessage],
        llm: Knot | LLMProvider,
        tools: Knot | Sequence[Tool],
        max_iterations: Knot | int = 10,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            messages=messages,
            llm=llm,
            tools=tools,
            max_iterations=max_iterations,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        messages: tuple[AgentMessage, ...] | list[AgentMessage],
        llm: LLMProvider,
        tools: Sequence[Tool],
        max_iterations: int = 10,
        **_: Any,
    ) -> Any:
        """Run the unrolled ReAct loop over the seed messages and return the final AgentResponse.

        Args:
            messages: The seed conversation messages to initialize the ReAct loop context.
            llm: The LLM provider used for each reasoning step.
            tools: The sequence of tools available to the agent.
            max_iterations: The maximum number of ReAct iterations to unroll.

        Returns:
            An AgentResponse extracted from the final accumulated message transcript.

        Raises:
            TypeError: If llm is not an LLMProvider or any tool is not a Tool.
            ValueError: If max_iterations is not a positive integer.
        """
        if not isinstance(llm, LLMProvider):
            raise TypeError(f"ReActLoop: llm must be an LLMProvider, got {type(llm).__name__}")
        if not isinstance(max_iterations, int) or max_iterations <= 0:
            raise ValueError(
                f"ReActLoop: max_iterations must be a positive int, got {max_iterations!r}"
            )
        tool_tuple = tuple(tools)
        for index, candidate in enumerate(tool_tuple):
            if not isinstance(candidate, Tool):
                raise TypeError(
                    f"ReActLoop: tools[{index}] must be a Tool, got {type(candidate).__name__}"
                )
        seed_messages = tuple(messages)
        seed = MessagesPassthrough(
            messages=seed_messages,
            _config=KnotConfig(id="seed"),
        )
        running_messages: Knot = seed
        already_terminated: Knot | bool = False
        for index in range(max_iterations):
            prior_terminated = already_terminated
            context_knot = ContextBuilder(
                messages=running_messages,
                _config=KnotConfig(id=f"context_{index}"),
            )
            step = ReActStepExecutor(
                context=context_knot,
                llm=llm,
                tools=tool_tuple,
                already_terminated=prior_terminated,
                _config=KnotConfig(id=f"step_{index}"),
            )
            running_messages = ReActStepAccumulator(
                prior=running_messages,
                step_output=step,
                already_terminated=prior_terminated,
                _config=KnotConfig(id=f"accum_{index}"),
            )
            already_terminated = ReActTerminationCheck(
                latest_response=step,
                max_iterations=max_iterations,
                current_iteration=index + 1,
                already_terminated=prior_terminated,
                _config=KnotConfig(id=f"gate_{index}"),
            )
        return ReActResponseExtractor(
            messages=running_messages,
            _config=KnotConfig(id="response"),
        )
