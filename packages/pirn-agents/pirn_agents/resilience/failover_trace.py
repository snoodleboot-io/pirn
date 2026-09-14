"""``FailoverTrace`` — surface a finished failover loop's :class:`FailoverResult`."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.resilience.failover_loop_state import FailoverLoopState
from pirn_agents.resilience.failover_result import FailoverResult


class FailoverTrace(Knot):
    """Project the loop's final state onto the trace it accumulated."""

    def __init__(
        self, *, state: Knot | FailoverLoopState, _config: KnotConfig, **kwargs: Any
    ) -> None:
        super().__init__(state=state, _config=_config, **kwargs)

    async def process(self, state: FailoverLoopState, **_: Any) -> FailoverResult:
        """Return ``state.result``.

        Args:
            state: The failover loop's final state.

        Returns:
            The accumulated :class:`FailoverResult`.
        """
        return state.result
