"""``RoundRobinResponseExtractor`` — final loop state to the public response.

The loop's output is the accumulated ``RoundRobinState``; ``RoundRobinReview``'s
contract is a bare :class:`AgentResponse`. This knot is the conversion, so the
pipeline returns a real sink rather than a ``Source`` closure wrapping a
precomputed value.

Internal API.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.specializations.multi_agent.round_robin_state import RoundRobinState
from pirn_agents.types.messaging.agent_response import AgentResponse


class RoundRobinResponseExtractor(Knot):
    """Convert the loop's final state into the pipeline's public response."""

    def __init__(
        self,
        *,
        state: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(state=state, _config=_config, **kwargs)

    async def process(self, state: Any, **_: Any) -> AgentResponse:
        """Extract the final revised response.

        Args:
            state: The loop's final accumulated state.

        Returns:
            The :class:`AgentResponse` as revised by the last reviewer to run.

        Raises:
            TypeError: If ``state`` is not the loop's state object.
        """
        if not isinstance(state, RoundRobinState):
            raise TypeError(
                "RoundRobinResponseExtractor: state must be a "
                f"RoundRobinState, got {type(state).__name__}"
            )
        return state.response
