"""``NullRunRecorder`` — pass-through recorder that always runs live I/O."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from pirn_agents.evaluation.run_recorder import RunRecorder


class NullRunRecorder(RunRecorder):
    """The default :class:`RunRecorder`: execute the work, record nothing.

    Used when no deterministic replay is configured — the runner behaves exactly
    as if it called the target directly. F29's cassette recorder replaces this to
    add record/replay determinism without changing the runner.
    """

    async def invoke(self, *, key: str, thunk: Callable[[], Awaitable[Any]]) -> Any:
        """Execute ``thunk`` live and return its result, ignoring ``key``."""
        return await thunk()
