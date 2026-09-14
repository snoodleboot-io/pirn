"""``ToolInvocation`` — one tool call whose ``ToolCall`` may arrive from upstream.

Since the ADR "agents speaks core" (WS1) a tool call *is* a knot:
``factory.for_call(call)`` constructs ``tool_cls(**call.arguments,
_config=KnotConfig(id=call.call_id, timeout=..., retry=...))`` and the engine
validates, schedules, retries, times out and records it like any other node.
An execution site that already holds the resolved ``ToolCall`` — a fan-out
executor, a ReAct step — constructs that knot directly.

``ToolInvocation`` is the thin :class:`~pirn.nodes.sub_tapestry.SubTapestry`
for the case where the call is itself the *output of an upstream knot* (a
planner, a router, a gated approval): ``process()`` receives the resolved
call, constructs the tool knot inside the inner tapestry, and returns it as
the sink, so the call's own ``Ok | Err | Skipped`` and lineage row are
recorded in the inner run under the call's id.

Its output is, for one deprecation cycle, the :class:`ToolResult` *view* of
that outcome — built through the single
:meth:`ToolResult.from_result` from the tool knot's ``Result`` and lineage
row — so every consumer of the pre-ADR shape keeps working unchanged.  A tool
that raised is therefore an ``ERROR`` view (the tool knot's own ``Err`` is
in lineage), a denied approval upstream skips this knot outright (core passes
a skipped sink through as ``Skipped``), and a call whose arguments the
declaration refuses is recorded as its own ``Err`` through
:class:`~pirn_agents.tools.tool_call_rejection.ToolCallRejection`.  The next
cycle drops the view and surfaces the tool knot's ``Result`` directly.

This container reports its one call through
:class:`~pirn_agents.observability.agent_call_recorder.AgentCallRecorder`
(ADR WS4a) as a ``"tool"`` event under *its own* id on the *outer* run — the
attribution a consumer correlating spans to the graph it wired expects — and
claims that report from the tool knot (``Tool._call_reported_by_container``)
so one call yields one event.  A tool knot wired directly (a fan-out) reports
itself.  The deprecated ``ToolInvocationHook`` seam is not consulted here.

Algorithm:
    1. ``process()`` receives the resolved ``tool`` (any spelling of a
       capability; validated into a :class:`ToolFactory`), ``call``,
       ``timeout`` and ``retry``.
    2. ``factory.for_call(call, timeout=..., retry=...)`` constructs the tool
       knot under the call's id — or, when the arguments are refused, a
       ``ToolCallRejection`` under the same id.
    3. The sink is an ``Aggregator`` over that knot with
       ``error_policy=RECEIVE_ERRORS``, whose ``combine`` builds the view from
       the call's ``Result``; ``__call__`` then attaches the call knot's
       lineage row (``latency``) from the inner run.
"""

from __future__ import annotations

import functools
import time
from collections.abc import Mapping
from typing import Any

from pirn.core.error_policy import ErrorPolicy
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_retry_policy import KnotRetryPolicy
from pirn.core.ok import Ok
from pirn.core.result import Result
from pirn.core.run_result import RunResult
from pirn.nodes.aggregator import Aggregator
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry

from pirn_agents.exceptions.tool_argument_validation_error import (
    ToolArgumentValidationError,
)
from pirn_agents.observability.agent_call_recorder import AgentCallRecorder
from pirn_agents.security.secret_redactor import SecretRedactor
from pirn_agents.tools.tool import Tool
from pirn_agents.tools.tool_call import ToolCall
from pirn_agents.tools.tool_call_rejection import ToolCallRejection
from pirn_agents.tools.tool_factory import ToolFactory
from pirn_agents.tools.tool_result import ToolResult


class ToolInvocation(SubTapestry):
    """Run one :class:`ToolCall` — possibly produced upstream — as a tool knot."""

    # The sink receives the call knot's ``Err`` and reports it in the view;
    # a failed call is that call's own recorded failure, not this knot's.
    _inner_failures_reach_sink = True

    def __init__(
        self,
        *,
        tool: Knot | ToolFactory | Any,
        call: Knot | ToolCall,
        timeout: Knot | float | None = None,
        retry: Knot | KnotRetryPolicy | None = None,
        approval_hook: Any = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        """Wire a single tool call as a graph node.

        Args:
            tool: The capability to call — a :class:`ToolFactory`, a ``Tool``
                class, a ``@ToolDecorator.decorate``/``@knot`` factory, or an upstream knot
                producing one.
            call: The :class:`ToolCall` to execute, either as a literal or as
                an upstream knot the engine resolves first.
            timeout: ``KnotConfig.timeout`` applied to the tool knot.
            retry: ``KnotConfig.retry`` applied to the tool knot.
            approval_hook: The
                :class:`~pirn_agents.agent.approval_hook.ApprovalHook` to
                consult when ``tool`` requires approval (PIR-865); ``None``
                uses the auto-approving default. Typed ``Any``: a bare,
                non-pydantic class core's eager per-input ``TypeAdapter``
                build cannot schema.
            _config: Framework metadata; ``id`` is required as for any knot.
        """
        super().__init__(
            tool=tool,
            call=call,
            timeout=timeout,
            retry=retry,
            approval_hook=approval_hook,
            _config=_config,
            **kwargs,
        )

    def _make_inner_tapestry(self) -> Tapestry:
        """A tapestry whose fallback ``traceback_filter`` redacts secrets.

        The enclosing run's own filter wins when it has one; a tool call run
        from a bare ``Tapestry()`` still never persists a credential-bearing
        traceback.
        """
        return Tapestry(traceback_filter=SecretRedactor.default_traceback_filter())

    async def process(
        self,
        tool: ToolFactory,
        call: ToolCall,
        timeout: float | None = None,
        retry: KnotRetryPolicy | None = None,
        approval_hook: Any = None,
        **_: Any,
    ) -> Knot:
        """Construct the tool knot for ``call`` and return the view-building sink.

        Either outcome is also reported through
        :class:`~pirn_agents.observability.agent_call_recorder.AgentCallRecorder`
        (ADR agents-speaks-core WS4a) — the emitter-path replacement for the old
        ``ToolInvocationHook``/``SpanEmittingToolInvocationHook`` seam, which only
        the *executors* fired around their own hand-rolled invocation, never this
        knot. Every tool call scheduled through the engine as a ``ToolInvocation``
        is observable this way, regardless of whether the caller configured a
        hook.

        Args:
            tool: The resolved capability.
            call: The resolved :class:`ToolCall`.
            timeout: Seconds one attempt of the call may take, or ``None``.
            retry: Retry policy for the call, or ``None`` for one attempt.
            approval_hook: The approval hook to consult when ``tool`` requires
                approval (PIR-865); see :meth:`ToolFactory.for_call`.

        Returns:
            The sink of the inner pipeline: an ``Aggregator`` over the call
            knot (receiving its raw ``Result``) whose output is the
            :class:`ToolResult` view.
        """
        factory = ToolFactory.of(tool)
        try:
            call_knot = factory.for_call(
                call, timeout=timeout, retry=retry, approval_hook=approval_hook
            )
        except ToolArgumentValidationError as exc:
            call_knot = ToolCallRejection(
                call=call, error=exc, _config=KnotConfig(id=ToolFactory.knot_id_for(call.call_id))
            )
        return Aggregator(
            combine=functools.partial(self._view, call.call_id, factory.requires_approval()),
            outcome=call_knot,
            _config=KnotConfig(id="outcome", error_policy=ErrorPolicy.RECEIVE_ERRORS),
        )

    @staticmethod
    def _view(call_id: str, gated: bool, *, outcome: Result[Any]) -> ToolResult:
        """Build the deprecated view from the call knot's ``Result``.

        ``gated`` is whether ``tool`` required approval for this call
        (PIR-865): the call knot's only possible parent besides its own
        arguments is the approval gate :meth:`ToolFactory.for_call` wires in
        that case, so a ``Skipped`` outcome can only be that gate closing.
        """
        return ToolResult.from_result(call_id, outcome, gated=gated)

    def _record_inner_run_meta(self, run_result: RunResult) -> None:
        """Publish the inner run's identifiers and keep its lineage for ``__call__``."""
        super()._record_inner_run_meta(run_result)
        self._mutable_inner_lineage = list(run_result.lineage)

    async def __call__(self, parent_results: Any) -> Result[Any]:
        """Run as a ``SubTapestry``, attach the call's lineage latency, report the call."""
        self._mutable_inner_lineage: list[Any] = []
        start = time.perf_counter()
        token = Tool._call_reported_by_container.set(True)
        try:
            result = await super().__call__(parent_results)
        finally:
            Tool._call_reported_by_container.reset(token)
        elapsed = time.perf_counter() - start
        if not isinstance(result, Ok) or not isinstance(result.value, ToolResult):
            return result
        view = result.value
        if view.latency is None:
            row = next(
                (
                    row
                    for row in self._mutable_inner_lineage
                    if row.knot_id == ToolFactory.knot_id_for(view.call_id)
                ),
                None,
            )
            if row is not None:
                view = view.with_latency(ToolResult.latency_of(row))
        call = parent_results.get("call") if isinstance(parent_results, Mapping) else None
        if not isinstance(call, ToolCall):
            call = self.config_values.get("call")
        await AgentCallRecorder.record(
            knot_id=self.knot_id,
            kind="tool",
            ok=view.succeeded,
            latency=view.latency if view.latency is not None else elapsed,
            detail=view.error,
            tool_name=call.tool_name if isinstance(call, ToolCall) else None,
            call_id=view.call_id,
        )
        return Ok(value=view)
