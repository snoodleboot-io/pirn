"""``CascadeResult`` — extract the final CascadeOutcome from chain state."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.specializations.routing._cascade_chain_state import CascadeChainState
from pirn_agents.specializations.routing.cascade_outcome import CascadeOutcome


class CascadeResult(Knot):
    """Extract the final :class:`CascadeOutcome` from the chain's state."""

    def __init__(
        self, *, state: Knot | CascadeChainState, _config: KnotConfig, **kwargs: Any
    ) -> None:
        super().__init__(state=state, _config=_config, **kwargs)

    async def process(self, state: CascadeChainState, **_: Any) -> CascadeOutcome:
        """Return the accepted outcome, or a best-effort exhausted outcome."""
        if state.accepted_outcome is not None:
            return state.accepted_outcome
        return CascadeOutcome(
            value=state.best_value,
            chosen=state.best_tier,
            succeeded=False,
            escalated=True,
            attempted=state.attempted,
            decisions=state.decisions,
            confidence=state.best_confidence,
        )
