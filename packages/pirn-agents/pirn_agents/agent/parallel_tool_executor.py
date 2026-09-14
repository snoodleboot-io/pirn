"""``ParallelToolExecutor`` — run many :class:`ToolCall`s concurrently, through the engine.

Dispatches an ordered sequence of :class:`ToolCall`s against a
:class:`~pirn_agents.tools.toolset.Toolset` as one inner pipeline: one tool
knot per call — ``factory.for_call(call, timeout=..., retry=...,
concurrency_group="tools")`` — under an ``Aggregator`` that receives every
call's ``Ok | Err | Skipped`` (ADR agents-speaks-core, WS1).  Everything the
pre-ADR version hand-rolled is the engine's now:

* **Bounded concurrency** — the inner tapestry's ``ConcurrencyLimits`` cap the
  ``"tools"`` group at ``max_concurrency``; the engine admits calls under it.
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

Output, for one deprecation cycle, is a tuple of :class:`ToolResult` views in
input order, built through the single :meth:`ToolResult.from_result`; a call
naming an unregistered tool, or whose arguments the declaration refuses, is
recorded through :class:`~pirn_agents.tools.tool_call_rejection.ToolCallRejection`.

References:
    - :class:`pirn.engine.governed_dispatch.GovernedDispatch`
    - :class:`pirn_agents.specializations.tool_use.parallel_tool_caller.ParallelToolCaller`
"""

from __future__ import annotations

import functools
import logging
import warnings
from collections.abc import Sequence
from typing import Any

from pirn.core.concurrency.concurrency_limits import ConcurrencyLimits
from pirn.core.error_policy import ErrorPolicy
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_retry_policy import KnotRetryPolicy
from pirn.core.parameter import Parameter
from pirn.core.result import Result
from pirn.nodes.aggregator import Aggregator
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry

from pirn_agents.exceptions.tool_argument_validation_error import (
    ToolArgumentValidationError,
)
from pirn_agents.exceptions.tool_not_found_error import ToolNotFoundError
from pirn_agents.llm.retry_policy import RetryPolicy
from pirn_agents.performance.concurrency_config import ConcurrencyConfig
from pirn_agents.security.secret_redactor import SecretRedactor
from pirn_agents.tools.tool_call import ToolCall
from pirn_agents.tools.tool_call_rejection import ToolCallRejection
from pirn_agents.tools.tool_factory import ToolFactory
from pirn_agents.tools.tool_result import ToolResult
from pirn_agents.tools.toolset import Toolset


class ParallelToolExecutor(SubTapestry):
    """Execute a batch of :class:`ToolCall`s as sibling knots under one ``Aggregator``.

    ``retry`` is a :class:`KnotRetryPolicy` applied to every call.  The
    pre-ADR ``retries`` count and agents ``retry_policy`` (a
    :class:`~pirn_agents.llm.retry_policy.RetryPolicy`) are still accepted
    for one cycle and translated: ``retries`` extra attempts on top of the
    first, with the policy's backoff shape.  ``rng``/``sleep`` (test seams of
    the hand-rolled loop) and ``hook`` (a
    :class:`~pirn_agents.tools.tool_invocation_hook.ToolInvocationHook`) are
    accepted and deprecated: backoff belongs to the engine, and a call's
    outcome is observable from its lineage row and the run's emitters.  A hook
    still fires ``on_start`` before the graph runs and ``on_finish`` from the
    combine, with a ``0.0`` latency, so an existing subscriber keeps its
    events for the cycle.
    """

    # Every call's ``Err`` is delivered to the Aggregator, not to this knot.
    _inner_failures_reach_sink = True

    def __init__(
        self,
        *,
        tool_calls: Knot | Sequence[ToolCall],
        toolset: Knot | Toolset,
        max_concurrency: Knot | int = ConcurrencyConfig.max_concurrency,
        timeout: Knot | float | None = None,
        retry: Knot | KnotRetryPolicy | None = None,
        retries: Knot | int = 0,
        retry_policy: Any = None,
        rng: Any = None,
        sleep: Any = None,
        hook: Any = None,
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
            retries=retries,
            retry_policy=retry_policy,
            rng=rng,
            sleep=sleep,
            hook=hook,
            approval_hook=approval_hook,
            _config=_config,
            **kwargs,
        )

    def _make_inner_tapestry(self) -> Tapestry:
        """The inner run: calls admitted under the ``"tools"`` group cap; secrets redacted.

        ``max_concurrency`` is read from this knot's literal inputs; when it
        arrives from an upstream knot instead it is unknown here and the
        batch runs unbounded.
        """
        max_concurrency = self.config_values.get("max_concurrency")
        limits = (
            ConcurrencyLimits(groups={"tools": max_concurrency})
            if isinstance(max_concurrency, int) and max_concurrency >= 1
            else None
        )
        return Tapestry(
            concurrency=limits, traceback_filter=SecretRedactor.default_traceback_filter()
        )

    async def process(
        self,
        tool_calls: Sequence[ToolCall],
        toolset: Toolset,
        max_concurrency: int,
        timeout: float | None = None,
        retry: KnotRetryPolicy | None = None,
        retries: int = 0,
        # ``retry_policy`` / ``hook`` are typed ``Any``: the agents
        # ``RetryPolicy`` and ``ToolInvocationHook`` are bare classes core's
        # eager per-input ``TypeAdapter`` build cannot schema.
        retry_policy: Any = None,
        rng: Any = None,
        sleep: Any = None,
        hook: Any = None,
        approval_hook: Any = None,
        **_: Any,
    ) -> Knot:
        """Wire one tool knot per call and return the view-building sink.

        Args:
            tool_calls: Ordered calls to execute; each element must be a
                :class:`ToolCall`.
            toolset: Registry the calls are dispatched against.
            max_concurrency: Maximum number of simultaneously in-flight calls;
                must be >= 1.
            timeout: Per-call time budget in seconds, or ``None`` to disable.
            retry: Retry policy applied to every call, or ``None``.
            retries: Deprecated: extra attempts granted to a failing call.
            retry_policy: Deprecated: agents ``RetryPolicy`` supplying the
                backoff shape for ``retries``.
            rng: Deprecated and ignored.
            sleep: Deprecated and ignored.
            hook: Deprecated :class:`ToolInvocationHook` fired around each call.
            approval_hook: The approval hook to consult for a call whose tool
                requires approval (PIR-865); see
                :meth:`~pirn_agents.tools.tool_factory.ToolFactory.for_call`.

        Returns:
            The sink of the inner pipeline: an ``Aggregator`` over one knot per
            call whose output — a tuple of :class:`ToolResult` views in input
            order — becomes this knot's output.

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
        self._warn_deprecated(rng=rng, sleep=sleep, hook=hook, retries=retries)
        policy = self._effective_retry(retry, retries, retry_policy)
        if not call_list:
            return Parameter("empty", tuple, default=(), _config=KnotConfig(id="empty"))

        per_call: dict[str, Knot] = {}
        used_ids: set[str] = set()
        for index, call in enumerate(call_list):
            knot_id = ToolFactory.knot_id_for(call.call_id)
            if knot_id in used_ids:
                knot_id = f"{knot_id}-{index}"
            used_ids.add(knot_id)
            per_call[f"call_{index}"] = self._call_knot(
                call, toolset, knot_id, timeout, policy, approval_hook
            )
            if hook is not None:
                self._fire_start(hook, call)
        return Aggregator(
            combine=functools.partial(self._views, call_list, toolset, hook),
            _config=KnotConfig(id="results", error_policy=ErrorPolicy.RECEIVE_ERRORS),
            **per_call,
        )

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
                _config=KnotConfig(id=knot_id, concurrency_group="tools"),
            )
        try:
            return factory.for_call(
                call,
                knot_id=knot_id,
                timeout=timeout,
                retry=retry,
                concurrency_group="tools",
                approval_hook=approval_hook,
            )
        except ToolArgumentValidationError as exc:
            return ToolCallRejection(
                call=call, error=exc, _config=KnotConfig(id=knot_id, concurrency_group="tools")
            )

    @staticmethod
    def _effective_retry(
        retry: KnotRetryPolicy | None, retries: int, retry_policy: Any
    ) -> KnotRetryPolicy | None:
        """``retry`` when given; else the deprecated ``retries``/``retry_policy`` pair translated."""
        if retry is not None:
            return retry
        if retries <= 0:
            return None
        shape = retry_policy if isinstance(retry_policy, RetryPolicy) else RetryPolicy()
        return KnotRetryPolicy(
            max_attempts=retries + 1,
            base_delay=shape.base_delay,
            max_delay=shape.max_delay,
            multiplier=shape.multiplier,
            jitter=shape.jitter,
            max_retry_after=shape.max_retry_after,
        )

    @staticmethod
    def _warn_deprecated(*, rng: Any, sleep: Any, hook: Any, retries: int) -> None:
        """One ``DeprecationWarning`` per deprecated input actually supplied."""
        if retries:
            warnings.warn(
                "ParallelToolExecutor(retries=..., retry_policy=...) is deprecated (ADR "
                "agents-speaks-core WS1): pass retry=KnotRetryPolicy(max_attempts=...)",
                DeprecationWarning,
                stacklevel=3,
            )
        if rng is not None or sleep is not None:
            warnings.warn(
                "ParallelToolExecutor(rng=..., sleep=...) are ignored (ADR agents-speaks-core "
                "WS1): the engine's GovernedDispatch owns the backoff",
                DeprecationWarning,
                stacklevel=3,
            )
        if hook is not None:
            warnings.warn(
                "ParallelToolExecutor(hook=...) is deprecated (ADR agents-speaks-core WS1): a "
                "call's outcome is its lineage row and the run's emitters",
                DeprecationWarning,
                stacklevel=3,
            )

    @staticmethod
    def _views(
        calls: Sequence[ToolCall], toolset: Toolset, hook: Any, **by_key: Result[Any]
    ) -> tuple[ToolResult, ...]:
        """Build the views in input order from each call's ``Result``; fire a hook's ``on_finish``.

        ``gated`` (PIR-865) is whether the call's tool requires approval: such
        a call's own knot has no possible parent besides its own arguments
        and the approval gate ``ToolFactory.for_call`` wires in, so its only
        possible ``Skipped`` cause is that gate closing.
        """
        views: list[ToolResult] = []
        for index, call in enumerate(calls):
            factory = toolset.get(call.tool_name)
            gated = factory.requires_approval() if factory is not None else False
            view = ToolResult.from_result(call.call_id, by_key[f"call_{index}"], gated=gated)
            views.append(view)
            if hook is not None:
                ParallelToolExecutor._fire_finish(hook, call, view)
        return tuple(views)

    @staticmethod
    def _fire_start(hook: Any, call: ToolCall) -> None:
        """Fire ``hook.on_start`` for ``call``, swallowing any hook exception."""
        try:
            hook.on_start(
                tool_name=call.tool_name,
                args_digest=ParallelToolExecutor._args_digest(call),
                call_id=call.call_id,
            )
        except Exception:
            logging.getLogger(__name__).warning(
                "ToolInvocationHook.on_start raised for call_id=%s; ignoring",
                call.call_id,
                exc_info=True,
            )

    @staticmethod
    def _args_digest(call: ToolCall) -> str:
        """A stable 16-hex-char content digest of ``call``'s arguments, or a sentinel."""
        from pirn.core.hashing import content_hash  # local: keeps the hot path import-free

        try:
            digest = content_hash(dict(call.arguments))
        except Exception:
            return "unhashable-args"
        return digest.split(":", 1)[-1][:16]

    @staticmethod
    def _fire_finish(hook: Any, call: ToolCall, view: ToolResult) -> None:
        """Fire ``hook.on_finish`` for ``view``, swallowing any hook exception."""
        try:
            hook.on_finish(
                tool_name=call.tool_name,
                call_id=call.call_id,
                status=view.status,
                latency=view.latency if view.latency is not None else 0.0,
            )
        except Exception:
            logging.getLogger(__name__).warning(
                "ToolInvocationHook.on_finish raised for call_id=%s; ignoring",
                call.call_id,
                exc_info=True,
            )
