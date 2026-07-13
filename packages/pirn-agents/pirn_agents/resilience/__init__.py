"""Reliability & resilience primitives (PAE-F21).

Provider-neutral, pure-stdlib async building blocks that keep a flaky provider,
tool, or network from taking down a whole run:

    * a per-endpoint :class:`~pirn_agents.resilience.circuit_breaker.CircuitBreaker`
      (closed/open/half-open) that fails fast instead of stalling every call,
    * an ordered :class:`~pirn_agents.resilience.failover_chain.FailoverChain`
      that reroutes on error, timeout, or open circuit,
    * a shared async
      :class:`~pirn_agents.resilience.token_bucket_rate_limiter.TokenBucketRateLimiter`,
    * a :class:`~pirn_agents.resilience.bulkhead.Bulkhead` that isolates
      concurrency into per-backend pools, and
    * idempotency-key assignment plus safe-retry classification for mutating
      tool calls.

Every class lives one-per-module and is imported from its concrete module path;
nothing here imports a backend, so ``import pirn_agents`` stays backend-free.
"""

from __future__ import annotations

__all__: list[str] = []
