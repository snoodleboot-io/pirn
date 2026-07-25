"""``AsyncFanoutEngine`` — shared per-item mechanics for bounded async fan-out.

Both :class:`~pirn_agents.parallel_tool_executor.ParallelToolExecutor` and
:class:`~pirn_agents.batch.map_agent.MapAgent` fan a workload out across bounded
concurrency, run each item to a terminal *result value* (never raising, so one
failing item cannot poison a sibling), and drain in-flight work on cancellation.
They duplicated the per-item loop: the timeout wrapper, the jittered exponential
backoff, the retry-with-terminal-timeout structure, and the cancel-and-drain.

This mixin owns those mechanics once. It deliberately does **not** own the
*scheduling*, which genuinely differs: ``ParallelToolExecutor`` runs a known set
of calls and returns results in input order (``asyncio.gather``), while
``MapAgent`` pulls a lazy stream under a dynamic limit and yields in completion
order (``asyncio.wait``). Each engine keeps its own scheduling loop and its own
result type — the mixin is generic over that result type ``R`` and takes
result-builder callbacks, so an outcome becomes a ``ToolResult`` or a
``BatchItemResult`` in the subclass without the base knowing either.

Contract: subclasses must set ``_retry_policy``, ``_rng`` and ``_sleep`` before
the mixin's methods run (both do so in their constructors). The mixin declares
them as annotations rather than initialising them, so a subclass that is also a
frozen ``Knot`` can set them before its own ``super().__init__`` freezes the
instance without an ``__init__`` ordering conflict.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterable
from typing import Generic, TypeVar

from pirn_agents.llm.retry_policy import RetryPolicy

R = TypeVar("R")


class AsyncFanoutEngine(Generic[R]):
    """Per-item timeout, retry/backoff, isolation, and cancel-drain for fan-out."""

    # Set by each subclass before these methods run (see the module docstring).
    _retry_policy: RetryPolicy
    _rng: Callable[[], float] | None
    _sleep: Callable[[float], Awaitable[None]]

    async def _backoff(self, attempt: int) -> None:
        """Sleep for the policy's delay before retry ``attempt`` (0-based)."""
        delay = self._retry_policy.backoff_delay(attempt, rng=self._rng)
        if delay > 0:
            await self._sleep(delay)

    @staticmethod
    async def _with_timeout(
        invoke: Callable[[], Awaitable[object]], timeout: float | None
    ) -> object:
        """Await ``invoke()``, bounding it by ``timeout`` seconds when set.

        Overrunning a set ``timeout`` raises :class:`TimeoutError` (``asyncio``'s
        timeout), which the retry loop treats as terminal.
        """
        if timeout is not None:
            async with asyncio.timeout(timeout):
                return await invoke()
        return await invoke()

    @staticmethod
    async def _drain_on_cancel(tasks: Iterable[asyncio.Task[R]]) -> None:
        """Cancel every in-flight task and await its unwind, swallowing errors.

        The caller re-raises :class:`asyncio.CancelledError` after this returns, so
        cancellation stays cooperative and no task is left running.
        """
        pending = list(tasks)
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)

    async def _run_with_retries(
        self,
        invoke: Callable[[], Awaitable[object]],
        *,
        timeout: float | None,
        retries: int,
        on_ok: Callable[[object, int], R],
        on_timeout: Callable[[int], R],
        on_error: Callable[[BaseException, int], R],
        before_attempt: Callable[[], Awaitable[None]] | None = None,
        on_exception: Callable[[BaseException], None] | None = None,
        on_success: Callable[[], None] | None = None,
    ) -> R:
        """Run ``invoke`` with per-attempt timeout and jittered-backoff retries.

        Every terminal outcome is turned into an ``R`` by the caller's builders, so
        this never raises except :class:`asyncio.CancelledError` (cooperative
        cancellation is preserved). A :class:`TimeoutError` under a configured
        ``timeout`` is terminal — never retried; any other exception is retried up
        to ``retries`` times, then becomes an error result.

        Args:
            invoke: Zero-arg async callable performing one attempt.
            timeout: Per-attempt time budget in seconds, or ``None`` to disable.
            retries: Extra attempts granted after the first on a retryable failure.
            on_ok: ``(value, attempts) -> R`` — build the success result.
            on_timeout: ``(attempts) -> R`` — build the terminal-timeout result.
            on_error: ``(exc, attempts) -> R`` — build the exhausted-error result.
            before_attempt: Optional async hook run at the top of every attempt
                (e.g. acquiring a rate-limiter token).
            on_exception: Optional sync hook run for every caught exception before
                the retry decision (e.g. reacting to a throttle signal).
            on_success: Optional sync hook run once the attempt succeeds (e.g.
                nudging an adaptive concurrency controller up).

        Returns:
            The ``R`` built by whichever terminal builder fires.
        """
        attempt = 0
        while True:
            if before_attempt is not None:
                await before_attempt()
            try:
                value = await self._with_timeout(invoke, timeout)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if on_exception is not None:
                    on_exception(exc)
                if timeout is not None and isinstance(exc, TimeoutError):
                    return on_timeout(attempt + 1)
                if attempt >= retries:
                    return on_error(exc, attempt + 1)
                await self._backoff(attempt)
                attempt += 1
                continue
            if on_success is not None:
                on_success()
            return on_ok(value, attempt + 1)
