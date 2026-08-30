"""``ParallelToolExecutor`` — run many :class:`ToolCall`s concurrently.

Extends the single-call :class:`pirn_agents.planning.tool_executor.ToolExecutor`
idea to a batch: it dispatches an ordered sequence of :class:`ToolCall`s
against a :class:`~pirn_agents.tools.toolset.Toolset`, running them concurrently up
to a caller-supplied ``max_concurrency`` bound. Each call carries its own
per-call timeout, jittered-backoff retry budget, and failure isolation, so one
slow, timing-out, or raising call never aborts its siblings.

Semantics
---------
* **Bounded concurrency** — an :class:`asyncio.Semaphore` caps the number of
  in-flight invocations at ``max_concurrency``; wall-clock time approaches the
  slowest call rather than the sum.
* **Per-call timeout** — when ``timeout`` is not ``None`` each invocation runs
  inside ``async with asyncio.timeout(timeout)``; overrunning it yields a
  :attr:`~pirn_agents.tools.tool_status.ToolStatus.TIMEOUT` result. Timeouts
  are *not* retried.
* **Retry** — non-timeout exceptions are retried up to ``retries`` extra times.
  The inter-attempt delay comes from a composed
  :class:`~pirn_agents.llm.retry_policy.RetryPolicy` (the single backoff-schedule
  source), not a hand-rolled formula.
* **Failure isolation** — every task converts its own outcome into a
  :class:`ToolResult`; :func:`asyncio.gather` therefore never observes a raw
  exception and no failing call cancels a sibling.
* **Cancellation** — cancelling the outer ``process`` coroutine cancels every
  in-flight task and re-raises :class:`asyncio.CancelledError`; it is never
  swallowed.

References:
    - :class:`pirn_agents.specializations.tool_use.parallel_tool_caller.ParallelToolCaller`
    - Python ``asyncio`` timeouts and semaphores:
      https://docs.python.org/3/library/asyncio-task.html#timeouts
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable, Sequence
from typing import Any, ClassVar

from pirn.connectors.dsn_scrubber import DsnScrubber
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.managers.exception_record import ExceptionRecord

from pirn_agents.agent.async_fanout_engine import AsyncFanoutEngine
from pirn_agents.exceptions.tool_not_found_error import ToolNotFoundError
from pirn_agents.exceptions.tool_timeout_error import ToolTimeoutError
from pirn_agents.llm.retry_policy import RetryPolicy
from pirn_agents.performance.concurrency_config import ConcurrencyConfig
from pirn_agents.serialization.canonical_json import CanonicalJson
from pirn_agents.serialization.opaque_policy import OpaquePolicy
from pirn_agents.tools.tool import Tool
from pirn_agents.tools.tool_call import ToolCall
from pirn_agents.tools.tool_invocation_hook import ToolInvocationHook
from pirn_agents.tools.tool_result import ToolResult
from pirn_agents.tools.tool_status import ToolStatus
from pirn_agents.tools.toolset import Toolset

# Reported as the argument digest when the arguments have no content-derived
# encoding (PIR-826). Deliberately NOT hex, so a consumer can distinguish it
# from a real 16-hex-char digest instead of being handed an address-derived
# value that looks like one.
_UNHASHABLE_ARGS_DIGEST = "unhashable-args"


class ParallelToolExecutor(AsyncFanoutEngine[ToolResult], Knot):
    """Execute a batch of :class:`ToolCall`s concurrently with isolation.

    The retry backoff shape is configured at construction time via a
    ``retry_policy`` (kept off the ``process`` signature because it tunes *how* a
    retry sleeps rather than *what* is executed). The policy is the single source
    of the backoff *schedule*; the retry *count* remains the separate ``retries``
    budget, which is a per-invocation concern.

    Observability is opt-in via ``hook``: an optional
    :class:`~pirn_agents.tools.tool_invocation_hook.ToolInvocationHook` fired once
    before and once after every per-call invocation. It defaults to ``None`` —
    when absent the per-call path does zero extra work (no digest is computed,
    no hook is called), keeping the hot path allocation-free. Because
    observability must never change the result path, any exception a hook
    raises is caught and logged rather than propagated, so a misbehaving hook
    cannot abort the batch.
    """

    # A tool's exception message routinely carries whatever it was talking to,
    # including a DSN. The single-call ``ToolExecutor`` has always scrubbed;
    # this batch path did not, so it wrote live credentials into
    # ``ToolResult.error`` AND into the ``ExceptionRecord`` that persists to
    # lineage/history. ``ExceptionRecord`` carries the message twice — in
    # ``message`` and again inside ``traceback_text`` — so both are scrubbed
    # (PIR-733).
    _scrubber: ClassVar[DsnScrubber] = DsnScrubber()

    @classmethod
    def _scrubbed_record(cls, tool_name: str, exc: BaseException) -> ExceptionRecord:
        """Return an :class:`ExceptionRecord` with credential markers removed.

        Copies the frozen record rather than reconstructing the exception, which
        would fail for any exception whose constructor takes more than a message.
        """
        raw = ExceptionRecord.for_knot(tool_name, exc)
        return raw.model_copy(
            update={
                "message": cls._scrubber.scrub(raw.message),
                "traceback_text": cls._scrubber.scrub(raw.traceback_text),
            }
        )

    def __init__(
        self,
        *,
        tool_calls: Knot | Sequence[ToolCall],
        toolset: Knot | Toolset,
        max_concurrency: int = ConcurrencyConfig.max_concurrency,
        timeout: float | None = None,
        retries: int = 0,
        retry_policy: RetryPolicy | None = None,
        rng: Callable[[], float] | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
        hook: ToolInvocationHook | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        # Set backoff policy, jitter/sleep seams, and the observability hook before
        # super().__init__ freezes the instance. Like the retry policy these are not
        # ``process`` parameters, so they must not be forwarded to the base
        # constructor (which validates kwargs against process).
        self._retry_policy = retry_policy if retry_policy is not None else RetryPolicy()
        self._rng = rng
        self._sleep: Callable[[float], Awaitable[None]] = (
            sleep if sleep is not None else asyncio.sleep
        )
        self._hook = hook
        super().__init__(
            tool_calls=tool_calls,
            toolset=toolset,
            max_concurrency=max_concurrency,
            timeout=timeout,
            retries=retries,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        tool_calls: Sequence[ToolCall],
        toolset: Toolset,
        max_concurrency: int,
        timeout: float | None,
        retries: int,
        **_: Any,
    ) -> tuple[ToolResult, ...]:
        """Run every call concurrently and collect results in input order.

        Args:
            tool_calls: Ordered calls to execute; each element must be a
                :class:`ToolCall`.
            toolset: Registry the calls are dispatched against.
            max_concurrency: Maximum number of simultaneously in-flight
                invocations; must be >= 1.
            timeout: Per-call time budget in seconds, or ``None`` to disable
                per-call timeouts.
            retries: Number of *extra* attempts granted to a call that raises
                a non-timeout exception.

        Returns:
            A tuple of :class:`ToolResult`, one per input call, in the same
            order as ``tool_calls``.

        Raises:
            TypeError: If any ``tool_calls`` element is not a
                :class:`ToolCall`, or ``toolset`` is not a :class:`Toolset`.
            ValueError: If ``max_concurrency`` is less than 1.
            asyncio.CancelledError: Propagated (after cancelling in-flight
                tasks) if the coroutine itself is cancelled.
        """
        call_list = list(tool_calls)
        for index, call in enumerate(call_list):
            if not isinstance(call, ToolCall):
                raise TypeError(
                    f"ParallelToolExecutor: tool_calls[{index}] must be a "
                    f"ToolCall, got {type(call).__name__}"
                )
        if not isinstance(toolset, Toolset):
            raise TypeError(
                f"ParallelToolExecutor: toolset must be a Toolset, got {type(toolset).__name__}"
            )
        if max_concurrency < 1:
            raise ValueError(
                f"ParallelToolExecutor: max_concurrency must be >= 1, got {max_concurrency}"
            )

        semaphore = asyncio.Semaphore(max_concurrency)
        tasks: list[asyncio.Task[ToolResult]] = [
            asyncio.create_task(self._run_one(call, toolset, semaphore, timeout, retries))
            for call in call_list
        ]
        try:
            gathered = await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            await self._drain_on_cancel(tasks)
            raise
        return tuple(gathered)

    async def _run_one(
        self,
        call: ToolCall,
        toolset: Toolset,
        semaphore: asyncio.Semaphore,
        timeout: float | None,
        retries: int,
    ) -> ToolResult:
        """Execute a single call under the shared semaphore, never raising.

        Every terminal outcome — not-found, success, timeout, or exhausted
        retries — is returned as a :class:`ToolResult` so the surrounding
        :func:`asyncio.gather` never sees a raw exception.
        :class:`asyncio.CancelledError` is the sole exception allowed to
        propagate, so cooperative cancellation still works.

        When a :class:`ToolInvocationHook` is configured it is fired once
        before dispatch (``on_start``) and once after the result is built
        (``on_finish``) for *every* terminal outcome. When no hook is
        configured this path does no extra work at all — the argument digest
        is not even computed — so observability is strictly zero-cost when
        absent. Hook exceptions are swallowed (see :meth:`_fire_start` /
        :meth:`_fire_finish`) so a raising hook never disturbs the result.
        """
        start = time.perf_counter()
        hook = self._hook
        async with semaphore:
            if hook is not None:
                self._fire_start(hook, call)
            result = await self._dispatch(call, toolset, timeout, retries, start)
            if hook is not None:
                self._fire_finish(hook, call, result)
            return result

    async def _dispatch(
        self,
        call: ToolCall,
        toolset: Toolset,
        timeout: float | None,
        retries: int,
        start: float,
    ) -> ToolResult:
        """Resolve and invoke ``call``, returning its terminal ``ToolResult``.

        Holds the same never-raising contract as :meth:`_run_one`: every
        outcome is converted to a :class:`ToolResult` and only
        :class:`asyncio.CancelledError` may propagate. ``start`` is the
        :func:`time.perf_counter` reading taken before the semaphore was
        acquired, so measured ``latency`` includes queue-wait time.
        """
        tool: Tool | None = toolset.get(call.tool_name)
        if tool is None:
            not_found = ToolNotFoundError(call.tool_name, call.call_id)
            return ToolResult(
                call_id=call.call_id,
                result=None,
                status=ToolStatus.ERROR,
                error=str(not_found),
                exception=type(self)._scrubbed_record(call.tool_name, not_found),
                latency=time.perf_counter() - start,
            )
        # Precomputed under the guard so the on_timeout builder (which fires only
        # when ``timeout`` is set) has a narrowed float; its message is static.
        timeout_error = (
            ToolTimeoutError(call.tool_name, timeout, call.call_id) if timeout is not None else None
        )
        return await self._run_with_retries(
            lambda: tool.invoke(call.arguments),
            timeout=timeout,
            retries=retries,
            on_ok=lambda value, _attempts: ToolResult(
                call_id=call.call_id,
                result=value,
                status=ToolStatus.OK,
                latency=time.perf_counter() - start,
            ),
            # PIR-724 widened these callbacks to receive the exception; PIR-794
            # is the tool path finally keeping it. The timeout branch reports
            # the domain message from ``timeout_error`` as before, but the
            # record captures the exception the engine actually raised — that
            # is where the traceback lives.
            on_timeout=lambda exc, _attempts: ToolResult(
                call_id=call.call_id,
                result=None,
                status=ToolStatus.TIMEOUT,
                error=str(timeout_error),
                exception=type(self)._scrubbed_record(call.tool_name, exc),
                latency=time.perf_counter() - start,
            ),
            # ``error`` is left to derive from the record, so the message and the
            # record cannot drift apart.
            on_error=lambda exc, _attempts: ToolResult(
                call_id=call.call_id,
                result=None,
                status=ToolStatus.ERROR,
                exception=type(self)._scrubbed_record(call.tool_name, exc),
                latency=time.perf_counter() - start,
            ),
        )

    def _fire_start(self, hook: ToolInvocationHook, call: ToolCall) -> None:
        """Fire ``hook.on_start`` for ``call``, swallowing any hook exception.

        The argument digest is a stable 16-hex-char SHA-256 prefix over the
        call's arguments — short, order-independent, and safe to record without
        exposing raw argument values. This method is only ever reached when a
        hook is configured, so the digest is never computed on the no-hook
        path. A raising hook is logged and ignored, never propagated.

        The digest now comes from the shared canonical seam rather than a local
        ``json.dumps``, so it agrees with every other content hash in the package
        (PIR-726/PIR-826). Its value therefore differs from the pre-PIR-826 one:
        the seam uses tight separators. Nothing persists this digest — it is
        handed to a hook for correlation — so that is a cosmetic change.

        Unlike :meth:`~pirn_agents.evaluation.trajectory_call_key.TrajectoryCallKey.args_key`,
        an argument that renders only as a memory address does **not** raise
        here. That would breach this method's contract — the digest is computed
        outside the ``try`` below, so a raise would propagate out of a purely
        observational call path and break tool execution, and only when a hook
        happened to be configured. Degrading to a sentinel keeps the event
        flowing and is honest: it says "no content-derived digest" rather than
        offering an address-derived one that looks like a digest and silently
        differs on the next identical call.
        """
        digest = self._args_digest(call)
        try:
            hook.on_start(tool_name=call.tool_name, args_digest=digest, call_id=call.call_id)
        except Exception:
            logging.getLogger(__name__).warning(
                "ToolInvocationHook.on_start raised for call_id=%s; ignoring",
                call.call_id,
                exc_info=True,
            )

    @staticmethod
    def _args_digest(call: ToolCall) -> str:
        """Return a 16-hex-char content digest of ``call``'s arguments.

        Args:
            call: The tool call whose arguments are being summarised.

        Returns:
            The first 16 hex characters of the canonical SHA-256 over the
            arguments, or :data:`_UNHASHABLE_ARGS_DIGEST` when an argument
            renders only as its own memory address and so has no content-derived
            encoding. The sentinel is not hex, so a consumer can tell the two
            apart rather than being handed a plausible-looking digest.
        """
        try:
            return CanonicalJson.digest(dict(call.arguments), policy=OpaquePolicy.STR_CONTENT)[:16]
        except TypeError:
            logging.getLogger(__name__).warning(
                "ParallelToolExecutor: arguments for call_id=%s contain a value with no "
                "content-derived rendering, so no stable digest exists; reporting %r",
                call.call_id,
                _UNHASHABLE_ARGS_DIGEST,
            )
            return _UNHASHABLE_ARGS_DIGEST

    def _fire_finish(self, hook: ToolInvocationHook, call: ToolCall, result: ToolResult) -> None:
        """Fire ``hook.on_finish`` for ``result``, swallowing any hook exception.

        Fired for every terminal outcome (ok, error, timeout, not-found). The
        measured ``latency`` is always set by the dispatch path; it is coerced
        to ``0.0`` only to satisfy the ``float`` contract should it ever be
        ``None``. A raising hook is logged and ignored, never propagated, so
        observability stays side-effect-free on the result path.
        """
        try:
            hook.on_finish(
                tool_name=call.tool_name,
                call_id=call.call_id,
                status=result.status,
                latency=result.latency if result.latency is not None else 0.0,
            )
        except Exception:
            logging.getLogger(__name__).warning(
                "ToolInvocationHook.on_finish raised for call_id=%s; ignoring",
                call.call_id,
                exc_info=True,
            )
