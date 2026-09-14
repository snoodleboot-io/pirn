"""Performance primitives: run budgets and cancellation.

This subpackage carries the cross-cutting levers the ADR names as first-class
performance requirements — a :class:`~pirn_agents.performance.run_budget.RunBudget`
(iterations / tokens / wall-clock deadline) with a cooperative
:class:`~pirn_agents.performance.cancellation_token.CancellationToken`.
Bounded concurrency is core's own ``KnotConfig(concurrency_group=...)`` +
``ConcurrencyLimits`` now; the former ``ConcurrencyConfig``/
``BackpressureSemaphore`` one-cycle shims that wrapped a private pool for a
non-engine caller are deleted (PIR-864).
"""

__all__: list[str] = []
