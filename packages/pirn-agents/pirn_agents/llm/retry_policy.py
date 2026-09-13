"""``RetryPolicy`` — jittered exponential backoff configuration.

A frozen, provider-neutral value describing how a
:class:`pirn_agents.llm.base_llm_provider.BaseLLMProvider` retries a failed
request: how many attempts, and how long to wait between them. The delay grows
exponentially and is capped, then optionally has *full jitter* applied
(``uniform(0, delay)``) to avoid synchronised retry storms across a batch of
concurrent calls.

:meth:`run` additionally owns the retry *loop* itself — the previously
hand-rolled ``while True`` drivers in
:class:`~pirn_agents.llm.http_transport.HttpTransport`,
:class:`~pirn_agents.retrieval.embeddings.base_embedding_provider.BaseEmbeddingProvider`
and :class:`~pirn_agents.mcp.mcp_connector.McpConnector` all delegate to it now
(the retired ``AsyncFanoutEngine`` did too), so
there is one place that decides "was this exception retryable, and how long do
we wait" (PIR-856).
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, TypeVar

from pirn.core.pirn_opaque_value import PirnOpaqueValue

T = TypeVar("T")


@dataclass(frozen=True)
class RetryPolicy(PirnOpaqueValue):
    """How many times, and how long, to back off between retries.

    Attributes
    ----------
    max_retries:
        Maximum number of *retries* after the first attempt (so total
        attempts is ``max_retries + 1``). ``0`` disables retrying.
    base_delay:
        The un-jittered delay before the first retry, in seconds.
    max_delay:
        Ceiling on the exponential delay, in seconds.
    multiplier:
        Growth factor applied per attempt (``2.0`` doubles each time).
    jitter:
        When ``True``, full jitter is applied: the returned delay is a
        uniform draw in ``[0, capped_delay)``.
    max_retry_after:
        Ceiling (seconds) on a server-supplied Retry-After hint, so a
        hostile/misconfigured value cannot block the caller unboundedly.
    """

    max_retries: int = 2
    base_delay: float = 0.05
    max_delay: float = 2.0
    multiplier: float = 2.0
    jitter: bool = True
    max_retry_after: float = 60.0

    def backoff_delay(self, attempt: int, *, rng: Callable[[], float] | None = None) -> float:
        """Return the delay before retry ``attempt`` (0-based), in seconds.

        Args:
            attempt: The 0-based retry index (0 is the first retry).
            rng: Optional zero-arg callable returning a float in ``[0, 1)``
                used for the jitter draw; defaults to :func:`random.random`.
                Injected in tests for deterministic delays.

        Returns:
            The capped exponential delay, with full jitter applied when
            :attr:`jitter` is set.
        """
        raw = self.base_delay * (self.multiplier**attempt)
        capped = min(self.max_delay, raw)
        if not self.jitter:
            return capped
        draw = rng() if rng is not None else random.random()
        return capped * draw

    async def run(
        self,
        thunk: Callable[[int], Awaitable[T]],
        *,
        is_retryable: Callable[[BaseException], bool] | None = None,
        retry_after: Callable[[BaseException], float | None] | None = None,
        delay_for: Callable[[int, BaseException], float] | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
        rng: Callable[[], float] | None = None,
    ) -> T:
        """Call ``thunk(attempt)`` until it succeeds or retries are exhausted.

        The single retry-loop driver every caller in this package now shares,
        replacing four independent hand-rolled ``while``/``for`` loops
        (PIR-856). Each caller supplies only the parts that genuinely differ:
        which exceptions are retryable, and how the delay before the next
        attempt is computed.

        Algorithm:
            1. Call ``thunk(attempt)`` with the 0-based attempt index.
            2. On success, return its value immediately.
            3. On :class:`asyncio.CancelledError`, propagate immediately —
               cooperative cancellation is never retried.
            4. On any other exception: re-raise it unchanged when
               ``is_retryable`` is supplied and returns ``False`` for it, or
               when ``attempt`` has already reached :attr:`max_retries`.
            5. Otherwise sleep, then retry with ``attempt + 1``. The delay is
               ``delay_for(attempt, exc)`` when supplied; else
               ``retry_after(exc)`` capped by :attr:`max_retry_after` when that
               hint is available; else :meth:`backoff_delay`.

        Args:
            thunk: Async callable performing one attempt; receives the 0-based
                attempt index so behaviour (e.g. a per-attempt timeout) may
                vary across attempts without closing over mutable state.
            is_retryable: Optional predicate deciding whether a caught
                exception should be retried. Defaults to "every ``Exception``
                is retryable" — :class:`asyncio.CancelledError` is a
                ``BaseException``, not an ``Exception``, so it is never
                subject to this predicate; it always propagates.
            retry_after: Optional callable extracting a server-supplied delay
                hint (e.g. an HTTP ``Retry-After`` header) from a caught
                exception. Ignored when ``delay_for`` is supplied.
            delay_for: Optional callable computing the full delay directly
                from ``(attempt, exc)``, overriding both ``retry_after`` and
                :meth:`backoff_delay`. For a caller with its own backoff
                shape (e.g. :class:`~pirn_agents.mcp.mcp_connector.McpConnector`'s
                additive jitter) that must keep its existing schedule rather
                than adopt this policy's multiplicative full jitter.
            sleep: Async sleep function used between retries; defaults to
                :func:`asyncio.sleep`.
            rng: Optional jitter source forwarded to :meth:`backoff_delay`;
                unused when ``delay_for`` is supplied.

        Returns:
            ``thunk``'s return value from whichever attempt first succeeds.

        Raises:
            Exception: The final attempt's exception, once ``is_retryable``
                rejects it or retries are exhausted.
        """
        sleeper = sleep if sleep is not None else asyncio.sleep
        attempt = 0
        while True:
            try:
                return await thunk(attempt)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if is_retryable is not None and not is_retryable(exc):
                    raise
                if attempt >= self.max_retries:
                    raise
                if delay_for is not None:
                    delay = delay_for(attempt, exc)
                else:
                    hint = retry_after(exc) if retry_after is not None else None
                    delay = (
                        min(hint, self.max_retry_after)
                        if hint is not None
                        else self.backoff_delay(attempt, rng=rng)
                    )
                await sleeper(delay)
                attempt += 1

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "max_retries": self.max_retries,
            "base_delay": self.base_delay,
            "max_delay": self.max_delay,
            "multiplier": self.multiplier,
            "jitter": self.jitter,
            "max_retry_after": self.max_retry_after,
        }
