"""``KnotRetryPolicy`` — how the engine re-dispatches a knot whose attempt failed.

A frozen value attached to a knot through ``KnotConfig.retry``.  The engine,
not the knot, owns the retry loop (``pirn.engine.governed_dispatch``): an
attempt that ends in ``Err`` is re-dispatched with the same inputs after a
backoff sleep on the event loop, until an attempt succeeds, the policy's
predicate rejects the failure, or ``max_attempts`` is spent.  Dispatchers
never see the loop, and ``Knot.__call__`` never sees it either — a retried
knot is simply called again.

The retry decision reads the ``ExceptionRecord`` an ``Err`` carries rather
than a live exception object.  That is deliberate: the record is what every
dispatcher hands back, including the process-boundary ones (Ray, Dask,
Celery) where the exception object never crosses back, so a policy written
against the record behaves identically wherever the knot runs.

Algorithm:
    Given ``n`` attempts already made (``n >= 1``) and the record ``r`` of
    the failed attempt:

    1. ``should_retry(n, r)`` is ``True`` iff ``n < max_attempts`` and
       ``is_retryable`` is unset or returns ``True`` for ``r``.
    2. The delay before retry ``k`` (0-based, ``k = n - 1``) is the
       server-supplied hint ``retry_after(r)`` capped by ``max_retry_after``
       when such a hint exists, else ``backoff_delay(k)``.
    3. ``backoff_delay(k)`` is exponential, capped, and — when ``jitter`` is
       set — drawn uniformly from ``[0, capped)`` (full jitter) so that a
       batch of concurrent knots failing together does not retry together.

Math:
    $$
    \\text{raw}_k = \\text{base\\_delay} \\cdot \\text{multiplier}^{k}
    \\qquad
    \\text{capped}_k = \\min(\\text{max\\_delay}, \\text{raw}_k)
    $$

    $$
    \\text{delay}_k = \\begin{cases}
        \\text{capped}_k \\cdot u,\\; u \\sim U[0, 1) & \\text{jitter} \\\\
        \\text{capped}_k & \\text{otherwise}
    \\end{cases}
    $$

References:
    [1] Marc Brooker, "Exponential Backoff And Jitter" (AWS Architecture
        Blog, 2015) — the full-jitter variant chosen here:
        https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/
    [2] Alternative: equal/decorrelated jitter from the same article; full
        jitter was chosen because it needs no per-caller state.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

from pirn.managers.exception_record import ExceptionRecord


class KnotRetryPolicy(BaseModel):
    """How many times, and how long apart, the engine re-dispatches a failed knot.

    Attributes:
        max_attempts: Most dispatches of the knot in one run, the first
            included.  ``1`` (the default) means no retry at all.
        base_delay: Un-jittered delay before the first retry, in seconds.
        max_delay: Ceiling on the exponential delay, in seconds.
        multiplier: Growth factor applied per retry; ``2.0`` doubles.
        jitter: Apply full jitter — a uniform draw in ``[0, capped)``.
        max_retry_after: Ceiling on a ``retry_after`` hint, in seconds, so a
            hostile or misconfigured hint cannot park a run indefinitely.
        is_retryable: Predicate over the failed attempt's ``ExceptionRecord``;
            ``None`` retries every ``Err``.  Excluded from ``model_dump``.
        retry_after: Extracts a delay hint (seconds) from the record, e.g. a
            parsed ``Retry-After`` header; ``None`` for no hint.  Excluded
            from ``model_dump``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    max_attempts: Annotated[int, Field(ge=1, strict=True)] = 1
    base_delay: Annotated[float, Field(ge=0)] = 0.05
    max_delay: Annotated[float, Field(ge=0)] = 2.0
    multiplier: Annotated[float, Field(ge=1)] = 2.0
    jitter: bool = True
    max_retry_after: Annotated[float, Field(ge=0)] = 60.0
    is_retryable: Annotated[
        Callable[[ExceptionRecord], bool] | None, Field(default=None, exclude=True)
    ] = None
    retry_after: Annotated[
        Callable[[ExceptionRecord], float | None] | None, Field(default=None, exclude=True)
    ] = None

    def backoff_delay(self, retry_index: int, *, rng: Callable[[], float] | None = None) -> float:
        """Return the exponential delay before retry *retry_index* (0-based), in seconds.

        Args:
            retry_index: ``0`` for the first retry, ``1`` for the second, ...
            rng: Zero-argument callable returning a float in ``[0, 1)`` used
                for the jitter draw; defaults to :func:`random.random`.
                Inject in tests for deterministic delays.

        Returns:
            The capped exponential delay, jittered when :attr:`jitter` is set.
        """
        capped = min(self.max_delay, self.base_delay * (self.multiplier**retry_index))
        if not self.jitter:
            return capped
        draw = rng() if rng is not None else random.random()
        return capped * draw

    def should_retry(self, attempts: int, record: ExceptionRecord) -> bool:
        """Whether the engine should dispatch again after *attempts* failed dispatches.

        Args:
            attempts: Dispatches made so far, the failed one included (``>= 1``).
            record: The failed attempt's exception record.

        Returns:
            ``True`` when budget remains and the failure is retryable.
        """
        if attempts >= self.max_attempts:
            return False
        return self.is_retryable is None or bool(self.is_retryable(record))

    def delay_before_retry(
        self,
        retry_index: int,
        record: ExceptionRecord,
        *,
        rng: Callable[[], float] | None = None,
    ) -> float:
        """Return how long to sleep before retry *retry_index*, in seconds.

        A ``retry_after`` hint, capped by :attr:`max_retry_after`, wins over
        the backoff schedule when the policy can extract one from *record*.

        Args:
            retry_index: ``0`` for the first retry, ``1`` for the second, ...
            record: The failed attempt's exception record.
            rng: Jitter source forwarded to :meth:`backoff_delay`.
        """
        hint = self.retry_after(record) if self.retry_after is not None else None
        if hint is not None:
            return min(float(hint), self.max_retry_after)
        return self.backoff_delay(retry_index, rng=rng)

    def __repr__(self) -> str:
        fields: dict[str, Any] = self.model_dump()
        body = ", ".join(f"{name}={value!r}" for name, value in fields.items())
        return f"KnotRetryPolicy({body})"
