"""``FallbackChainResult`` — extract the final FallbackResult from state."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.specializations.routing.fallback_chain_state import FallbackChainState
from pirn_agents.specializations.routing.fallback_result import FallbackResult


class FallbackChainResult(Knot):
    """Extract the final :class:`FallbackResult` from the chain's state."""

    def __init__(
        self, *, state: Knot | FallbackChainState, _config: KnotConfig, **kwargs: Any
    ) -> None:
        super().__init__(state=state, _config=_config, **kwargs)

    async def process(self, state: FallbackChainState, **_: Any) -> FallbackResult:
        """Return the successful result, or an exhausted-chain result."""
        return FallbackResult(
            succeeded=state.chosen is not None,
            chosen=state.chosen,
            result=state.succeeded_result,
            attempted=state.attempted,
            skipped=state.skipped,
        )
