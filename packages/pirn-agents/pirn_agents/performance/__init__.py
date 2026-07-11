"""Performance primitives: run budgets, cancellation, and concurrency config.

This subpackage carries the cross-cutting levers the ADR names as first-class
performance requirements — a :class:`~pirn_agents.performance.run_budget.RunBudget`
(iterations / tokens / wall-clock deadline) with a cooperative
:class:`~pirn_agents.performance.cancellation_token.CancellationToken`, and a
shared :class:`~pirn_agents.performance.concurrency_config.ConcurrencyConfig`
plus :class:`~pirn_agents.performance.backpressure_semaphore.BackpressureSemaphore`
that tool executors and provider call sites consume instead of hard-coding
their own limits.
"""

__all__: list[str] = []
