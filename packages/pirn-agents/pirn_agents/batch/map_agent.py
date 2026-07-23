"""``MapAgent`` — map an agent over a dataset with per-item isolation.

The batch/fleet counterpart to F1's single-run concurrency: where
:class:`~pirn_agents.parallel_tool_executor.ParallelToolExecutor` fans a handful
of tool calls out for one agent turn, :class:`MapAgent` runs *one* agent over an
arbitrarily large stream of inputs. It is a streaming engine, not a
single-return :class:`~pirn.core.knot.Knot`: :meth:`run` is an async generator
that yields each :class:`BatchItemResult` the instant that item settles, so a
10k-item batch never has to be resident in memory at once.

Guarantees
----------
* **Per-item isolation** — a single item raising (or exhausting its retry
  budget, or timing out) is captured as an ``ERROR``/``TIMEOUT``
  :class:`BatchItemResult`; it never cancels or poisons its siblings.
* **Bounded in-flight + backpressure** — at most ``concurrency`` agent runs are
  ever in flight; the input iterable is pulled *lazily*, one item at a time, only
  as a slot frees, so a lazy/expensive input stream is never over-consumed.
* **Completion-order streaming** — results are yielded as each settles (not in
  input order), keeping latency-to-first-result low and memory flat.
* **Cancellation** — cancelling the :meth:`run` generator cancels every in-flight
  item and re-raises :class:`asyncio.CancelledError`; it is never swallowed.

The per-item agent is injected as a plain ``run_item`` coroutine callable
(``async (item) -> output``) rather than a concrete agent type, keeping the
engine provider-neutral and trivially testable with a stub double. Wrap a real
nested agent with a thin adapter over
:meth:`pirn_agents.agent_invoker.AgentInvoker.invoke` at the call site.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable

from pirn_agents.batch.adaptive_concurrency_controller import AdaptiveConcurrencyController
from pirn_agents.batch.batch_checkpointer import BatchCheckpointer
from pirn_agents.batch.batch_item_result import BatchItemResult
from pirn_agents.batch.batch_item_status import BatchItemStatus
from pirn_agents.batch.batch_progress import BatchProgress
from pirn_agents.batch.rate_limit_signal import RateLimitSignal
from pirn_agents.llm.retry_policy import RetryPolicy
from pirn_agents.resilience.token_bucket_rate_limiter import TokenBucketRateLimiter


class MapAgent:
    """Stream an agent's outputs over a dataset with bounded, isolated fan-out."""

    def __init__(
        self,
        run_item: Callable[[object], Awaitable[object]],
        *,
        concurrency: int = 8,
        timeout: float | None = None,
        retries: int = 0,
        key_fn: Callable[[object], str] | None = None,
        rate_limiter: TokenBucketRateLimiter | None = None,
        concurrency_controller: AdaptiveConcurrencyController | None = None,
        checkpointer: BatchCheckpointer | None = None,
        checkpoint_every: int = 1,
        retry_policy: RetryPolicy | None = None,
        rng: Callable[[], float] | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        """Build the batch runner.

        Args:
            run_item: The per-item agent callable — ``async (item) -> output``.
            concurrency: Maximum number of simultaneously in-flight items; the
                dispatch bound. Must be >= 1. Also the hard ceiling for the
                adaptive controller.
            timeout: Per-item time budget in seconds, or ``None`` to disable.
                Timeouts are terminal (never retried).
            retries: Extra attempts granted to an item that raises a non-timeout
                exception. Must be >= 0.
            key_fn: Maps an input item to a stable string key (for de-dup on
                resume). Defaults to the item's stream index.
            rate_limiter: An optional shared F21
                :class:`~pirn_agents.resilience.token_bucket_rate_limiter.TokenBucketRateLimiter`.
                When set, every attempt acquires one token before running, so the
                whole batch is paced under a provider quota; a
                :class:`RateLimitSignal` also pauses it for the upstream
                ``Retry-After``.
            concurrency_controller: An optional
                :class:`AdaptiveConcurrencyController`. When set the live dispatch
                bound follows its AIMD limit (capped at ``concurrency``): it
                scales down on a throttle and back up on success.
            checkpointer: An optional :class:`BatchCheckpointer` over an F14
                store. When set, :meth:`run` loads prior progress on start
                (skipping already-completed items as ``SKIPPED``) and persists
                each newly-completed key so a killed batch resumes mid-way.
            checkpoint_every: Persist a checkpoint after this many newly-completed
                items (a final flush always runs). Must be >= 1.
            retry_policy: The single backoff-schedule source for retry delays;
                defaults to a stock :class:`~pirn_agents.llm.retry_policy.RetryPolicy`.
                Only its delay schedule is consumed here — the retry *count* is the
                separate ``retries`` budget above.
            rng: Zero-arg ``[0, 1)`` source for the policy's jitter draw; injected
                in tests for deterministic delays. Defaults to the policy's own.
            sleep: Async sleep used for retry backoff; injected in tests so
                backoff advances deterministically. Defaults to
                :func:`asyncio.sleep`.

        Raises:
            TypeError: If ``run_item`` is not callable, or ``rate_limiter`` /
                ``concurrency_controller`` are of the wrong type.
            ValueError: If ``concurrency`` < 1 or ``retries`` < 0.
        """
        if not callable(run_item):
            raise TypeError(f"MapAgent: run_item must be callable, got {type(run_item).__name__}")
        if isinstance(concurrency, bool) or not isinstance(concurrency, int) or concurrency < 1:
            raise ValueError(f"MapAgent: concurrency must be an int >= 1, got {concurrency!r}")
        if isinstance(retries, bool) or not isinstance(retries, int) or retries < 0:
            raise ValueError(f"MapAgent: retries must be an int >= 0, got {retries!r}")
        if rate_limiter is not None and not isinstance(rate_limiter, TokenBucketRateLimiter):
            raise TypeError(
                f"MapAgent: rate_limiter must be a TokenBucketRateLimiter or None, "
                f"got {type(rate_limiter).__name__}"
            )
        if concurrency_controller is not None and not isinstance(
            concurrency_controller, AdaptiveConcurrencyController
        ):
            raise TypeError(
                f"MapAgent: concurrency_controller must be an AdaptiveConcurrencyController "
                f"or None, got {type(concurrency_controller).__name__}"
            )
        if checkpointer is not None and not isinstance(checkpointer, BatchCheckpointer):
            raise TypeError(
                f"MapAgent: checkpointer must be a BatchCheckpointer or None, "
                f"got {type(checkpointer).__name__}"
            )
        if (
            isinstance(checkpoint_every, bool)
            or not isinstance(checkpoint_every, int)
            or checkpoint_every < 1
        ):
            raise ValueError(
                f"MapAgent: checkpoint_every must be an int >= 1, got {checkpoint_every!r}"
            )
        self._run_item = run_item
        self._concurrency = concurrency
        self._timeout = timeout
        self._retries = retries
        self._key_fn = key_fn
        self._rate_limiter = rate_limiter
        self._controller = concurrency_controller
        self._checkpointer = checkpointer
        self._checkpoint_every = checkpoint_every
        self._retry_policy = retry_policy if retry_policy is not None else RetryPolicy()
        self._rng = rng
        self._sleep = sleep if sleep is not None else asyncio.sleep
        self._completed_keys: frozenset[str] = frozenset()

    @property
    def concurrency(self) -> int:
        """The configured maximum number of in-flight items."""
        return self._concurrency

    def _limit(self) -> int:
        """The live dispatch bound — the adaptive limit, capped at ``concurrency``."""
        if self._controller is None:
            return self._concurrency
        return max(1, min(self._concurrency, self._controller.limit()))

    def _key_for(self, index: int, item: object) -> str:
        if self._key_fn is None:
            return str(index)
        key = self._key_fn(item)
        if not isinstance(key, str) or not key:
            raise TypeError(f"MapAgent: key_fn must return a non-empty str, got {key!r}")
        return key

    async def run(self, inputs: Iterable[object]) -> AsyncIterator[BatchItemResult]:
        """Run the agent over ``inputs``, yielding each result as it settles.

        Args:
            inputs: The dataset to map over. Consumed lazily — one item is pulled
                only when an in-flight slot is free — so the stream is never
                materialised in full and backpressure flows to the producer.

        Yields:
            One :class:`BatchItemResult` per input item, in completion order.

        Raises:
            asyncio.CancelledError: Propagated (after cancelling in-flight items)
                if the generator is cancelled.
        """
        progress = await self._load_progress()
        source = enumerate(inputs)
        pending: set[asyncio.Task[BatchItemResult]] = set()
        exhausted = False
        since_checkpoint = 0
        try:
            while True:
                exhausted = self._fill(source, pending, exhausted)
                if not pending:
                    break
                done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    result = task.result()
                    if self._checkpointer is not None and result.status is BatchItemStatus.OK:
                        progress = progress.with_completed(result.key)
                        since_checkpoint += 1
                        if since_checkpoint >= self._checkpoint_every:
                            await self._checkpointer.save(progress)
                            since_checkpoint = 0
                    yield result
        except asyncio.CancelledError:
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            raise
        if self._checkpointer is not None and since_checkpoint > 0:
            await self._checkpointer.save(progress)

    async def _load_progress(self) -> BatchProgress:
        """Load prior progress (seeding the resume skip-set), or start empty."""
        if self._checkpointer is None:
            self._completed_keys = frozenset()
            return BatchProgress(batch_id="batch")
        progress = await self._checkpointer.load()
        self._completed_keys = progress.completed_keys
        return progress

    def _fill(
        self,
        source: object,
        pending: set[asyncio.Task[BatchItemResult]],
        exhausted: bool,
    ) -> bool:
        """Top up ``pending`` up to the current limit, returning exhaustion.

        Pulls at most enough items to reach ``_limit()`` in-flight; each pull is
        the lazy ``next()`` that carries backpressure to the input producer.
        """
        if exhausted:
            return True
        while len(pending) < self._limit():
            try:
                index, item = next(source)  # type: ignore[call-overload]
            except StopIteration:
                return True
            key = self._key_for(index, item)
            pending.add(asyncio.ensure_future(self._run_one(index, item, key)))
        return False

    async def _run_one(self, index: int, item: object, key: str) -> BatchItemResult:
        """Run a single item to a terminal result, never raising (except cancel).

        Every outcome — success, timeout, or exhausted retries — is converted to
        a :class:`BatchItemResult` so the surrounding :func:`asyncio.wait` never
        observes a raw exception and no failing item cancels a sibling.
        :class:`asyncio.CancelledError` is the sole exception allowed to
        propagate, preserving cooperative cancellation.
        """
        if key in self._completed_keys:
            return BatchItemResult(index=index, key=key, status=BatchItemStatus.SKIPPED, attempts=0)
        start = time.perf_counter()
        attempt = 0
        while True:
            if self._rate_limiter is not None:
                await self._rate_limiter.acquire()
            try:
                output = await self._invoke(item)
            except asyncio.CancelledError:
                raise
            except RateLimitSignal as exc:
                self._on_throttle(exc)
                if attempt >= self._retries:
                    return self._error_result(index, key, exc, attempt + 1, start)
                await self._backoff(attempt)
                attempt += 1
                continue
            except TimeoutError as exc:
                if self._timeout is not None:
                    return BatchItemResult(
                        index=index,
                        key=key,
                        status=BatchItemStatus.TIMEOUT,
                        error=f"item timed out after {self._timeout}s",
                        attempts=attempt + 1,
                        latency=time.perf_counter() - start,
                    )
                if attempt >= self._retries:
                    return self._error_result(index, key, exc, attempt + 1, start)
                await self._backoff(attempt)
                attempt += 1
                continue
            except Exception as exc:
                if attempt >= self._retries:
                    return self._error_result(index, key, exc, attempt + 1, start)
                await self._backoff(attempt)
                attempt += 1
                continue
            if self._controller is not None:
                self._controller.on_success()
            return BatchItemResult(
                index=index,
                key=key,
                status=BatchItemStatus.OK,
                output=output,
                attempts=attempt + 1,
                latency=time.perf_counter() - start,
            )

    def _on_throttle(self, signal: RateLimitSignal) -> None:
        """React to an upstream throttle: scale concurrency down, pause the bucket.

        Backs the adaptive controller off multiplicatively and, when a shared
        rate limiter and a ``Retry-After`` are both present, floors token
        acquisition until the hint elapses so no sibling item hammers the
        throttled provider in the meantime.
        """
        if self._controller is not None:
            self._controller.on_throttle()
        if self._rate_limiter is not None and signal.retry_after is not None:
            self._rate_limiter.pause_for(signal.retry_after)

    async def _invoke(self, item: object) -> object:
        """Invoke the per-item agent, applying the per-item timeout if set."""
        if self._timeout is not None:
            async with asyncio.timeout(self._timeout):
                return await self._run_item(item)
        return await self._run_item(item)

    @staticmethod
    def _error_result(
        index: int, key: str, exc: BaseException, attempts: int, start: float
    ) -> BatchItemResult:
        return BatchItemResult(
            index=index,
            key=key,
            status=BatchItemStatus.ERROR,
            error=str(exc) or type(exc).__name__,
            attempts=attempts,
            latency=time.perf_counter() - start,
        )

    async def _backoff(self, attempt: int) -> None:
        delay = self._retry_policy.backoff_delay(attempt, rng=self._rng)
        if delay > 0:
            await self._sleep(delay)
