"""``TerminationCheck`` — decide whether the agent loop should stop."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.types.agent_response import AgentResponse


class TerminationCheck(Knot):
    """Returns ``True`` when the agent loop should terminate.

    Termination fires when the response carries a terminal
    ``finish_reason`` (``"stop"``) or when the iteration counter has
    reached ``max_iterations``.
    """

    def __init__(
        self,
        *,
        response: Knot,
        max_iterations: int,
        current_iteration: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(max_iterations, int) or max_iterations <= 0:
            raise ValueError(
                "TerminationCheck: max_iterations must be a positive int, "
                f"got {max_iterations!r}"
            )
        super().__init__(
            response=response,
            max_iterations=max_iterations,
            current_iteration=current_iteration,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        response: AgentResponse,
        max_iterations: int,
        current_iteration: int,
        **_: Any,
    ) -> bool:
        """Return True when the response signals stop or the iteration limit is reached.

        Args:
            response: The agent response to inspect for a terminal finish reason.
            max_iterations: Maximum number of iterations before forced termination.
            current_iteration: The current iteration count.

        Returns:
            True if the response finish reason is "stop" or the iteration limit is reached.

        Raises:
            TypeError: If response is not an AgentResponse or current_iteration is not an int.
        """
        if not isinstance(response, AgentResponse):
            raise TypeError(
                "TerminationCheck: response must be an AgentResponse, "
                f"got {type(response).__name__}"
            )
        if not isinstance(current_iteration, int):
            raise TypeError(
                "TerminationCheck: current_iteration must be an int, "
                f"got {type(current_iteration).__name__}"
            )
        if response.finish_reason == "stop":
            return True
        return current_iteration >= max_iterations
