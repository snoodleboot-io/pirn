"""``_FanoutRunner`` — the composed fan-out engine ``ParallelToolExecutor`` drives.

Split out of ``parallel_tool_executor.py`` for the one-class-per-file rule (PIR-856).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from pirn_agents.agent.async_fanout_engine import AsyncFanoutEngine
from pirn_agents.llm.retry_policy import RetryPolicy
from pirn_agents.tools.tool_result import ToolResult


class _FanoutRunner(AsyncFanoutEngine[ToolResult]):
    """Composed — not inherited — per-call retry/timeout mechanics.

    ``ParallelToolExecutor`` is a frozen :class:`~pirn.core.knot.Knot` (Rule 4:
    no instance state for inputs), so the retry policy, jitter source, and
    sleep function :class:`AsyncFanoutEngine` needs can no longer live on
    ``self`` set before ``super().__init__()`` freezes the instance —
    multiply inheriting ``AsyncFanoutEngine`` alongside ``Knot`` required
    exactly that ordering. A fresh, short-lived instance of this holder is
    built inside :meth:`ParallelToolExecutor.process` instead, from that
    call's resolved config values, so no retry state is ever stored on the
    knot itself (PIR-856).
    """

    def __init__(
        self,
        *,
        retry_policy: RetryPolicy,
        rng: Callable[[], float] | None,
        sleep: Callable[[float], Awaitable[None]],
    ) -> None:
        self._retry_policy = retry_policy
        self._rng = rng
        self._sleep = sleep
