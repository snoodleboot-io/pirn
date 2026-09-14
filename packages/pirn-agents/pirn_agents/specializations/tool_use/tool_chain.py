"""``ToolChain`` — execute a fixed sequence of tools, piping output to input, through the engine.

Takes an initial :class:`ToolCall` and a sequence of tool capabilities.
Executes the first call, feeds its result as ``input`` to the next tool in
the chain, and so on. Returns the :class:`ToolResult` view from wherever the
chain actually stopped — the final tool's success, or the first tool that
failed.

Every step is a tool knot — ``factory.for_call(call)`` (ADR agents-speaks-core,
WS1) — so each call in the chain gets its own lineage/history/``Ok|Err|Skipped``
instead of being awaited inline.  A failed step is that step's own ``Err``,
and the engine's default error policy does the short-circuit: every knot
downstream of it — the next call, the next step, to the end of the chain —
is :class:`~pirn.core.skipped.Skipped` automatically, with no gate to
write by hand.

Algorithm:
    1. Receive resolved ``initial_call`` and ``tools`` at process time.
    2. Validate that ``tools`` is non-empty and each entry is a capability.
    3. The first step is ``tools[0].for_call(initial_call)``.
    4. For each subsequent tool: wire an :class:`~pirn.nodes.aggregator.Aggregator`
       that builds the next :class:`ToolCall` from the previous step's raw
       output — or returns ``Skipped`` when that step failed — then the next
       step as a :class:`~pirn_agents.tools.tool_invocation.ToolInvocation`
       over that upstream call.
    5. Return an :class:`Aggregator` over every step's own result, configured
       with ``error_policy=RECEIVE_ERRORS`` so its ``combine`` sees each
       step's raw ``Ok | Err | Skipped`` and picks the *last* step that ran —
       the final success or the first failure — as the chain's outcome.

References:
    - :class:`pirn_agents.tools.tool_factory.ToolFactory`
    - :class:`pirn_agents.tools.tool_invocation.ToolInvocation`
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
from pirn.core.skipped import Skipped
from pirn.nodes.aggregator import Aggregator
from pirn.tapestry import Tapestry

from pirn_agents.exceptions.tool_argument_validation_error import (
    ToolArgumentValidationError,
)
from pirn_agents.security.secret_redactor import SecretRedactor
from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.tools.tool_call import ToolCall
from pirn_agents.tools.tool_call_rejection import ToolCallRejection
from pirn_agents.tools.tool_factory import ToolFactory
from pirn_agents.tools.tool_invocation import ToolInvocation
from pirn_agents.tools.tool_result import ToolResult


class ToolChain(AgentPipeline):
    """Execute a sequence of tools, through the engine, passing each output to the next."""

    # A failed step is delivered to the terminal Aggregator, not to this knot.
    _inner_failures_reach_sink = True

    def __init__(
        self,
        *,
        initial_call: Knot | ToolCall,
        tools: Knot | Sequence[Any],
        approval_hook: Any = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            initial_call=initial_call,
            tools=tools,
            approval_hook=approval_hook,
            _config=_config,
            **kwargs,
        )

    def _make_inner_tapestry(self) -> Tapestry:
        """A tapestry whose fallback ``traceback_filter`` redacts secrets."""
        return Tapestry(traceback_filter=SecretRedactor.default_traceback_filter())

    async def process(
        self,
        initial_call: ToolCall,
        tools: Sequence[ToolFactory],
        approval_hook: Any = None,
        **_: Any,
    ) -> Knot:
        """Wire the chain and return the knot that resolves to its terminal result.

        Args:
            initial_call: The first ToolCall to execute, which seeds the chain.
            tools: The ordered capabilities to execute.
            approval_hook: The approval hook to consult for a step whose tool
                requires approval (PIR-865); see
                :meth:`~pirn_agents.tools.tool_factory.ToolFactory.for_call`.

        Returns:
            The sink of the inner pipeline: an :class:`~pirn.nodes.aggregator.Aggregator`
            over every step's own result, whose output — the :class:`ToolResult`
            view of whichever step the chain actually stopped at — becomes
            this knot's output.

        Raises:
            TypeError: If initial_call is not a ToolCall or any entry in tools is not a capability.
            ValueError: If tools is empty.
        """
        tool_list = list(tools)
        if not tool_list:
            raise ValueError("ToolChain: tools must not be empty")
        factories: list[ToolFactory] = []
        for index, tool in enumerate(tool_list):
            try:
                factories.append(ToolFactory.of(tool))
            except TypeError as exc:
                raise TypeError(
                    f"ToolChain: tools[{index}] must be a Tool, got {type(tool).__name__}"
                ) from exc

        call_id = initial_call.call_id
        steps: dict[str, Knot] = {}
        try:
            previous_step: Knot = factories[0].for_call(
                initial_call, knot_id="step-0", approval_hook=approval_hook
            )
        except ToolArgumentValidationError as exc:
            previous_step = ToolCallRejection(
                call=initial_call, error=exc, _config=KnotConfig(id="step-0")
            )
        steps["step_0"] = previous_step

        for index, factory in enumerate(factories[1:], start=1):
            next_call = Aggregator(
                combine=functools.partial(
                    self._build_next_call, tool_name=factory.name, call_id=call_id
                ),
                previous=previous_step,
                _config=KnotConfig(id=f"next-call-{index}"),
            )
            previous_step = ToolInvocation(
                tool=factory,
                call=next_call,
                approval_hook=approval_hook,
                _config=KnotConfig(id=f"step-{index}"),
            )
            steps[f"step_{index}"] = previous_step

        return Aggregator(
            combine=functools.partial(self._pick_terminal, call_id),
            _config=KnotConfig(id="chain-result", error_policy=ErrorPolicy.RECEIVE_ERRORS),
            **steps,
        )

    @staticmethod
    def _build_next_call(previous: Any, *, tool_name: str, call_id: str) -> ToolCall | Skipped:
        """Build the next step's :class:`ToolCall` from the previous step's raw output.

        A previous step that is a failed :class:`ToolResult` view (a
        ``ToolInvocation`` reports its call's ``Err`` as a view for the
        cycle) stops the chain: returning ``Skipped`` skips this call and
        everything downstream of it, exactly as a raw ``Err`` upstream would.
        """
        if isinstance(previous, ToolResult):
            if previous.error is not None:
                return Skipped(reason="previous_step_failed")
            previous = previous.result
        return ToolCall(tool_name=tool_name, arguments={"input": previous}, call_id=call_id)

    @staticmethod
    def _pick_terminal(call_id: str, **results: Result[Any]) -> ToolResult:
        """Return the view of the last step that actually ran.

        Every step after the chain first stops is ``Skipped`` (the default
        error policy's propagation), never ``Ok`` or ``Err`` — so the last
        non-skipped step is exactly the one the chain stopped at, whether
        that is the final tool's success or a middle tool's failure (a
        ``ToolInvocation`` step's own raw ``Result`` is ``Ok`` even when the
        ``ToolResult`` view it carries reports an error, so it is never
        itself ``Skipped``). The one case with *no* non-skipped step is
        step 0 denied outright (PIR-865): step 0 is a bare tool knot, not a
        ``ToolInvocation``, so a denied approval leaves it genuinely
        ``Skipped`` and every later step cascades from it — the chain
        stopped at the very first step, so that is the terminal. Its skip
        reason is the approval check's own ``"approval_denied"``, propagated
        by core to the tool knot (PIR-872), so the view names it directly.
        """
        ordered = sorted(results.items(), key=lambda item: int(item[0].rsplit("_", 1)[1]))
        non_skipped = [result for _, result in ordered if not isinstance(result, Skipped)]
        terminal = non_skipped[-1] if non_skipped else ordered[0][1]
        if isinstance(terminal, Ok) and isinstance(terminal.value, ToolResult):
            return terminal.value
        return ToolResult.from_result(call_id, terminal)
