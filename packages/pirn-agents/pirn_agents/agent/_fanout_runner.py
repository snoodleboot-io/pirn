"""``_FanoutRunner`` — deprecated (one cycle); ``ParallelToolExecutor`` no longer drives a fan-out engine.

Since the ADR "agents speaks core" (WS1) the executor wires one tool knot per
call under an ``Aggregator`` and the engine owns concurrency, per-call timeout
and retry (``KnotConfig.timeout`` / ``KnotConfig.retry`` run by
``GovernedDispatch``).  Nothing composes this holder any more; it stays
importable for the cycle as the ``AsyncFanoutEngine`` it always was, and
warns on construction.
"""

from __future__ import annotations

import warnings
from collections.abc import Awaitable, Callable

from pirn_agents.agent.async_fanout_engine import AsyncFanoutEngine
from pirn_agents.llm.retry_policy import RetryPolicy
from pirn_agents.tools.tool_result import ToolResult


class _FanoutRunner(AsyncFanoutEngine[ToolResult]):  # pyright: ignore[reportUnusedClass]  # imported by tests/test_async_fanout_engine.py
    """Deprecated composed per-call retry/timeout mechanics (unused since WS1)."""

    def __init__(
        self,
        *,
        retry_policy: RetryPolicy,
        rng: Callable[[], float] | None,
        sleep: Callable[[float], Awaitable[None]],
    ) -> None:
        warnings.warn(
            "_FanoutRunner is deprecated (ADR agents-speaks-core WS1): per-call timeout and "
            "retry are KnotConfig.timeout / KnotConfig.retry, run by the engine",
            DeprecationWarning,
            stacklevel=2,
        )
        self._retry_policy = retry_policy
        self._rng = rng
        self._sleep = sleep
