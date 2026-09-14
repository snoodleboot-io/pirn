"""``ParallelToolExecutor`` — run many :class:`ToolCall`s concurrently, through the engine.

Dispatches an ordered sequence of :class:`ToolCall`s against a
:class:`~pirn_agents.tools.toolset.Toolset` as one inner pipeline: one tool
knot per call — ``factory.for_call(call, timeout=..., retry=...,
concurrency_group="tools")`` — under an ``Aggregator`` that receives every
call's ``Ok | Err | Skipped`` (ADR agents-speaks-core, WS1).  Everything the
pre-ADR version hand-rolled is the engine's now:

* **Bounded concurrency** — the inner run's ``ConcurrencyLimits`` cap the
  ``"tools"`` group at the *resolved* ``max_concurrency`` (a literal or an
  upstream knot's output), passed to ``NestedRunKnot._run_inner``; the engine
  admits calls under it, chained beneath any enclosing cap.
* **Per-call timeout** — ``KnotConfig.timeout``: an attempt that outlives it
  is cancelled and recorded as ``Err(KnotTimeoutError)``, which the
  :class:`ToolResult` view reports as ``TIMEOUT``.
* **Retry** — ``KnotConfig.retry`` with a :class:`~pirn.core.knot_retry_policy.KnotRetryPolicy`
  (the previously deferred inter-attempt backoff is core's
  ``GovernedDispatch`` now); the attempt count lands in the call's lineage
  ``extra["attempts"]``.
* **Failure isolation** — a failed call is its own recorded ``Err``; the
  ``Aggregator`` combines the batch regardless, so a sibling never skips.
* **Cancellation** — cancelling the run cancels every in-flight call (core).

The executor is a :class:`~pirn.nodes.nested_run_knot.NestedRunKnot`: its
``process()`` builds the fan-out, runs it through ``_run_inner`` with the cap,
and returns the views. An empty batch starts no inner run at all.

Output is a tuple of :class:`ToolResult` views in input order, built through
the single :meth:`ToolResult.from_result`; a call naming an unregistered
tool, or whose arguments the declaration refuses, is recorded through
:class:`~pirn_agents.tools.tool_call_rejection.ToolCallRejection`.

References:
    - :class:`pirn.engine.governed_dispatch.GovernedDispatch`
    - :class:`pirn_agents.specializations.tool_use.parallel_tool_caller.ParallelToolCaller`
"""

from __future__ import annotations

import functools
from collections.abc import Sequence
from typing import Any, ClassVar

from pirn.core.concurrency.concurrency_limits import ConcurrencyLimits
from pirn.core.error_policy import ErrorPolicy
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_retry_policy import KnotRetryPolicy
from pirn.core.result import Result
from pirn.nodes.aggregator import Aggregator
from pirn.nodes.nested_run_knot import NestedRunKnot
from pirn.tapestry import Tapestry

from pirn_agents.exceptions.tool_argument_validation_error import (
    ToolArgumentValidationError,
)
from pirn_agents.exceptions.tool_not_found_error import ToolNotFoundError
from pirn_agents.security.secret_redactor import SecretRedactor
from pirn_agents.tools.tool_call import ToolCall
from pirn_agents.tools.tool_call_rejection import ToolCallRejection
from pirn_agents.tools.tool_factory import ToolFactory
from pirn_agents.tools.tool_result import ToolResult
from pirn_agents.tools.toolset import Toolset


class ParallelToolExecutor(NestedRunKnot):
    """Execute a batch of :class:`ToolCall`s as sibling knots under one ``Aggregator``.

    ``retry`` is a :class:`KnotRetryPolicy` applied to every call; backoff
    between attempts belongs to the engine's ``GovernedDispatch``.  A call's
    outcome is observable from its lineage row and the run's emitters.
    """

    # Every call's ``Err`` is delivered to the Aggregator, not to this knot.
    _inner_failures_reach_sink: ClassVar[bool] = True

    #: The concurrency group every call is admitted under.
    _group: ClassVar[str] = "tools"

    #: The inner run's combining knot id.
    _results_id: ClassVar[str] = "results"

    def __init__(
        self,
        *,
        tool_calls: Knot | Sequence[ToolCall],
        toolset: Knot | Toolset,
        max_concurrency: Knot | int = 8,
        timeout: Knot | float | None = None,
        retry: Knot | KnotRetryPolicy | None = None,
        approval_hook: Any = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            tool_calls=tool_calls,
            toolset=toolset,
            max_concurrency=max_concurrency,
            timeout=timeout,
            retry=retry,
            approval_hook=approval_hook,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        tool_calls: Sequence[ToolCall],
        toolset: Toolset,
        max_concurrency: int,
        timeout: float | None = None,
        retry: KnotRetryPolicy | None = None,
        approval_hook: Any = None,
        **_: Any,
    ) -> tuple[ToolResult, ...]:
        """Run one tool knot per call under the concurrency cap and return the views.

        Args:
            tool_calls: Ordered calls to execute; each element must be a
                :class:`ToolCall`.
            toolset: Registry the calls are dispatched against.
            max_concurrency: Maximum number of simultaneously in-flight calls;
                must be >= 1.
            timeout: Per-call time budget in seconds, or ``None`` to disable.
            retry: Retry policy applied to every call, or ``None``.
            approval_hook: The approval hook to consult for a call whose tool
                requires approval (PIR-865); see
                :meth:`~pirn_agents.tools.tool_factory.ToolFactory.for_call`.

        Returns:
            One :class:`ToolResult` view per call, in input order, combined by
            an ``Aggregator`` over the calls' results.

        Raises:
            TypeError: If any ``tool_calls`` element is not a
                :class:`ToolCall`, or ``toolset`` is not a :class:`Toolset`.
            ValueError: If ``max_concurrency`` is less than 1.
        """
        call_list = list(tool_calls)
        for index, call in enumerate(call_list):
            if not isinstance(call, ToolCall):
                raise TypeError(
                    f"ParallelToolExecutor: tool_calls[{index}] must be a "
                    f"ToolCall, got {type(call).__name__}"
                )
        # Kept, not redundant: ReWooPipeline wires this knot with
        # KnotConfig(validate_io=False), so this guard is the only protection
        # ``toolset`` gets there.
        if not isinstance(toolset, Toolset):
            raise TypeError(
                f"ParallelToolExecutor: toolset must be a Toolset, got {type(toolset).__name__}"
            )
        if max_concurrency < 1:
            raise ValueError(
                f"ParallelToolExecutor: max_concurrency must be >= 1, got {max_concurrency}"
            )
        if not call_list:
            return ()

        with Tapestry(traceback_filter=SecretRedactor.default_traceback_filter()) as inner:
            per_call: dict[str, Knot] = {}
            used_ids: set[str] = set()
            for index, call in enumerate(call_list):
                knot_id = ToolFactory.knot_id_for(call.call_id)
                if knot_id in used_ids:
                    knot_id = f"{knot_id}-{index}"
                used_ids.add(knot_id)
                per_call[f"call_{index}"] = self._call_knot(
                    call, toolset, knot_id, timeout, retry, approval_hook
                )
            Aggregator(
                combine=functools.partial(self._views, call_list),
                _config=KnotConfig(id=self._results_id, error_policy=ErrorPolicy.RECEIVE_ERRORS),
                **per_call,
            )
        run = await self._run_inner(
            inner, concurrency=ConcurrencyLimits(groups={self._group: max_concurrency})
        )
        return run.outputs[self._results_id]

    @staticmethod
    def _call_knot(
        call: ToolCall,
        toolset: Toolset,
        knot_id: str,
        timeout: float | None,
        retry: KnotRetryPolicy | None,
        approval_hook: Any = None,
    ) -> Knot:
        """The knot that runs ``call``: the tool knot, or a rejection recorded as its ``Err``."""
        factory = toolset.get(call.tool_name)
        if factory is None:
            return ToolCallRejection(
                call=call,
                error=ToolNotFoundError(call.tool_name, call.call_id),
                _config=KnotConfig(id=knot_id, concurrency_group=ParallelToolExecutor._group),
            )
        try:
            return factory.for_call(
                call,
                knot_id=knot_id,
                timeout=timeout,
                retry=retry,
                concurrency_group=ParallelToolExecutor._group,
                approval_hook=approval_hook,
            )
        except ToolArgumentValidationError as exc:
            return ToolCallRejection(
                call=call,
                error=exc,
                _config=KnotConfig(id=knot_id, concurrency_group=ParallelToolExecutor._group),
            )

    @staticmethod
    def _views(calls: Sequence[ToolCall], **by_key: Result[Any]) -> tuple[ToolResult, ...]:
        """Build the views in input order from each call's ``Result``."""
        return tuple(
            ToolResult.from_result(call.call_id, by_key[f"call_{index}"])
            for index, call in enumerate(calls)
        )
