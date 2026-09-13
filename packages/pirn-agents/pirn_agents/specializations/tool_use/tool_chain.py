"""``ToolChain`` — execute a fixed sequence of tools, piping output to input, through the engine.

Takes an initial :class:`ToolCall` and a sequence of :class:`Tool` instances.
Executes the first call, feeds its result as ``input`` to the next tool in
the chain, and so on. Returns the :class:`ToolResult` from wherever the
chain actually stopped — the final tool's success, or the first tool that
failed.

Every step is a :class:`~pirn_agents.tools.tool_invocation.ToolInvocation`,
the same knot :class:`~pirn_agents.planning.tool_executor.ToolExecutor` and
:class:`~pirn_agents.agent.parallel_tool_executor.ParallelToolExecutor` use,
so each call in the chain gets its own lineage/history/``Ok|Err|Skipped``
instead of being awaited inline (PIR-856).

Algorithm:
    1. Receive resolved ``initial_call`` and ``tools`` at process time.
    2. Validate that ``tools`` is non-empty and each entry is a :class:`Tool`.
    3. Validate that ``initial_call`` is a :class:`ToolCall`.
    4. Wire ``ToolInvocation`` for ``tools[0]`` against ``initial_call``.
    5. For each subsequent tool: wire a :class:`~pirn.nodes.gate.gate.Gate`
       on the previous step's output, open only when that step's
       :class:`ToolResult` has :attr:`~pirn_agents.tools.tool_status.ToolStatus.OK`;
       when closed, everything downstream — the next call, the next
       invocation, and so on to the end of the chain — is
       :class:`~pirn.core.skipped.Skipped` automatically (``error_policy``'s
       default, ``SKIP_IF_PARENT_FAILED``, propagates a skip through every
       knot that depends on it). When open, wire an
       :class:`~pirn.nodes.aggregator.Aggregator` that builds the next
       :class:`ToolCall` from the previous result, then the next
       ``ToolInvocation`` against it.
    6. Return an :class:`Aggregator` over every step's own result, configured
       with ``error_policy=RECEIVE_ERRORS`` so its ``combine`` sees each
       step's raw ``Ok | Skipped`` and can distinguish "this step ran" from
       "the chain had already stopped before this step" — picking the
       *last* step whose result is ``Ok`` is exactly the tool where the chain
       stopped, whether that is the final success or the first failure,
       because every step after a failure is ``Skipped``, never ``Ok``.

References:
    - :class:`pirn_agents.tools.tool_invocation.ToolInvocation`
    - :class:`pirn.nodes.gate.gate.Gate`
    - :class:`pirn.core.error_policy.ErrorPolicy`
"""

from __future__ import annotations

import functools
from collections.abc import Sequence
from typing import Any

from pirn.core.error_policy import ErrorPolicy
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.ok import Ok
from pirn.core.result import Result
from pirn.nodes.aggregator import Aggregator
from pirn.nodes.gate.gate import Gate

from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.tools.tool import Tool
from pirn_agents.tools.tool_call import ToolCall
from pirn_agents.tools.tool_invocation import ToolInvocation
from pirn_agents.tools.tool_result import ToolResult
from pirn_agents.tools.tool_status import ToolStatus


class ToolChain(AgentPipeline):
    """Execute a sequence of tools, through the engine, passing each output to the next."""

    def __init__(
        self,
        *,
        initial_call: Knot | ToolCall,
        tools: Knot | Sequence[Tool],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(initial_call=initial_call, tools=tools, _config=_config, **kwargs)

    async def process(
        self,
        initial_call: ToolCall,
        tools: Sequence[Tool],
        **_: Any,
    ) -> Knot:
        """Wire the chain and return the knot that resolves to its terminal result.

        Args:
            initial_call: The first ToolCall to execute, which seeds the chain.
            tools: The ordered sequence of Tool instances to execute.

        Returns:
            The sink of the inner pipeline: an :class:`~pirn.nodes.aggregator.Aggregator`
            over every step's own result, whose output — the :class:`ToolResult`
            of whichever step the chain actually stopped at — becomes this
            knot's output.

        Raises:
            TypeError: If initial_call is not a ToolCall or any entry in tools is not a Tool.
            ValueError: If tools is empty.
        """
        tool_list = list(tools)
        if not tool_list:
            raise ValueError("ToolChain: tools must not be empty")
        for index, tool in enumerate(tool_list):
            if not isinstance(tool, Tool):
                raise TypeError(
                    f"ToolChain: tools[{index}] must be a Tool, got {type(tool).__name__}"
                )
        if not isinstance(initial_call, ToolCall):
            raise TypeError(
                f"ToolChain: initial_call must be a ToolCall, got {type(initial_call).__name__}"
            )

        call_id = initial_call.call_id
        steps: dict[str, Knot] = {}
        previous_step: Knot = ToolInvocation(
            tool=tool_list[0], call=initial_call, _config=KnotConfig(id="step-0")
        )
        steps["step_0"] = previous_step

        for index, tool in enumerate(tool_list[1:], start=1):
            gate = Gate(
                input=previous_step,
                predicate=self._step_succeeded,
                _config=KnotConfig(id=f"gate-{index - 1}"),
            )
            next_call = Aggregator(
                combine=functools.partial(
                    self._build_next_call, tool_name=tool.name, call_id=call_id
                ),
                previous=gate,
                _config=KnotConfig(id=f"next-call-{index}"),
            )
            previous_step = ToolInvocation(
                tool=tool, call=next_call, _config=KnotConfig(id=f"step-{index}")
            )
            steps[f"step_{index}"] = previous_step

        return Aggregator(
            combine=self._pick_terminal,
            _config=KnotConfig(id="chain-result", error_policy=ErrorPolicy.RECEIVE_ERRORS),
            **steps,
        )

    @staticmethod
    def _step_succeeded(result: ToolResult) -> bool:
        """Gate predicate: only chain into the next tool on an OK result."""
        return result.status is ToolStatus.OK

    @staticmethod
    def _build_next_call(previous: ToolResult, *, tool_name: str, call_id: str) -> ToolCall:
        """Build the next step's :class:`ToolCall` from the previous step's raw output."""
        return ToolCall(tool_name=tool_name, arguments={"input": previous.result}, call_id=call_id)

    @staticmethod
    def _pick_terminal(**results: Result[ToolResult]) -> ToolResult:
        """Return the result of the last step whose own result is ``Ok``.

        Every step after the chain first fails is ``Skipped`` (the closed
        gate's default ``error_policy`` propagation), never ``Ok`` — so the
        last ``Ok`` step is exactly the one the chain stopped at, whether
        that is the final tool's success or the first tool's failure.
        """
        ordered = sorted(results.items(), key=lambda item: int(item[0].rsplit("_", 1)[1]))
        terminal: ToolResult | None = None
        for _, result in ordered:
            if isinstance(result, Ok):
                terminal = result.value
        if terminal is None:
            # Unreachable in practice: step_0 has no gate in front of it, so
            # it is never Skipped and always contributes an Ok result.
            raise RuntimeError("ToolChain: no step produced a result")
        return terminal
