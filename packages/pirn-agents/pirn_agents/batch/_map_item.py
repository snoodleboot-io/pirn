"""``_MapItem`` — one batch item as a real, engine-scheduled knot.

ADR agents-speaks-core, WS4b: the unit ``MapAgent`` used to dispatch itself
(a bare coroutine inside ``asyncio.wait``) becomes one knot per item, so
admission, timeout, and retry are the engine's ``AdmissionGate`` /
``GovernedDispatch`` rather than a hand-rolled scheduler. The caller still
supplies a plain ``async (item) -> output`` callable — authoring a ``Knot``
subclass per batch is not required.

Rate limiting is applied here, inside ``process()``, rather than as a
separate wrapping layer, because ``GovernedDispatch`` calls ``process()``
fresh on every retry attempt (PIR-849's dispatch loop re-invokes
``Knot.__call__`` per attempt): acquiring a token and reacting to a
:class:`~pirn_agents.batch.rate_limit_signal.RateLimitSignal` here runs
exactly once per attempt, matching the pre-migration scheduler's
``before_attempt`` / ``on_exception`` hooks.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from pirn.core.knot import Knot

from pirn_agents.batch.rate_limit_signal import RateLimitSignal


class _MapItem(Knot):
    """Runs one batch item through the injected per-item callable.

    Inputs (all config values — this knot has no ``Knot`` parents):

    * ``item`` — the element being processed.
    * ``run_item`` — the caller's ``async (item) -> output`` callable.
    * ``rate_limiter`` — an optional shared
      :class:`~pirn_agents.resilience.token_bucket_rate_limiter.TokenBucketRateLimiter`
      acquired before every attempt. Typed ``Any`` (not the concrete class)
      because ``Knot`` builds a Pydantic ``TypeAdapter`` for every annotated
      ``process()`` parameter, and an arbitrary, non-Pydantic class raises
      ``PydanticSchemaGenerationError`` there without ``arbitrary_types_allowed``.
    * ``on_throttle`` — an optional callable invoked with the
      :class:`RateLimitSignal`'s ``retry_after`` (or ``None``) when the item
      raises one, so an :class:`~pirn_agents.batch.adaptive_concurrency_controller.AdaptiveConcurrencyController`
      can react to the *specific* signal — something the engine's coarse
      ``AdmissionEvent.outcome`` cannot distinguish from an ordinary failure.
    """

    async def process(
        self,
        item: Any,
        run_item: Callable[[Any], Awaitable[Any]],
        rate_limiter: Any = None,
        on_throttle: Callable[[float | None], None] | None = None,
        **_: Any,
    ) -> Any:
        if rate_limiter is not None:
            await rate_limiter.acquire()
        try:
            return await run_item(item)
        except RateLimitSignal as exc:
            if on_throttle is not None:
                on_throttle(exc.retry_after)
            if rate_limiter is not None and exc.retry_after is not None:
                rate_limiter.pause_for(exc.retry_after)
            raise
