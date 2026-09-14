"""``ConstitutionalResultExtractor`` — final loop state to the public response.

The loop's output is the accumulated ``ConstitutionalState``;
``ConstitutionalFilter``'s contract is a compliant ``AgentResponse`` (or a
raised ``ConstitutionalViolationError`` on exhaustion). This knot is the
conversion.

Internal API. See PIR-856.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.specializations.reflection._constitutional_state import ConstitutionalState
from pirn_agents.specializations.reflection.constitutional_violation_error import (
    ConstitutionalViolationError,
)
from pirn_agents.types.messaging.agent_response import AgentResponse


class ConstitutionalResultExtractor(Knot):
    """Convert the loop's final state into a compliant :class:`AgentResponse`."""

    def __init__(
        self,
        *,
        state: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(state=state, _config=_config, **kwargs)

    async def process(self, state: ConstitutionalState, **_: Any) -> AgentResponse:
        """Return the compliant response, or raise once revisions are exhausted.

        Args:
            state: The loop's final accumulated state.

        Returns:
            The compliant :class:`AgentResponse`.

        Raises:
            ConstitutionalViolationError: If the loop exhausted its revision
                attempts without reaching compliance.
        """
        if not state.compliant:
            raise ConstitutionalViolationError(
                "ConstitutionalFilter: response still violates principles after "
                f"{state.attempts} revision(s)"
            )
        return AgentResponse(content=state.current_content)
