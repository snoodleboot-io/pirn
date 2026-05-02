"""``ReActTerminationGate`` — decide whether a ReAct loop should stop.

The gate inspects the trailing assistant message produced by the most
recent :class:`ReActStepExecutor` and emits a boolean ``terminate``
signal when:

* the message contains the ``Final Answer:`` marker, *or*
* the current iteration count has reached ``max_iterations``.

The signal is a plain ``bool`` so downstream knots can branch on it
without needing to introspect a richer record. The gate is lightweight
on purpose: ReAct termination is a policy decision and the surrounding
:class:`ReActLoop` already drives the iteration topology by unrolling
a fixed number of step knots.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.types.agent_message import AgentMessage


class ReActTerminationGate(Knot):
    """Stops the ReAct loop on a final-answer marker or iteration cap."""

    _final_answer_marker: str = "Final Answer:"

    def __init__(
        self,
        *,
        latest_response: Knot,
        max_iterations: int,
        current_iteration: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(max_iterations, int) or max_iterations <= 0:
            raise ValueError(
                "ReActTerminationGate: max_iterations must be a positive int, "
                f"got {max_iterations!r}"
            )
        if not isinstance(current_iteration, (Knot, int)):
            raise TypeError(
                "ReActTerminationGate: current_iteration must be a Knot or int, "
                f"got {type(current_iteration).__name__}"
            )
        if isinstance(current_iteration, int) and current_iteration < 0:
            raise ValueError(
                "ReActTerminationGate: current_iteration must be non-negative, "
                f"got {current_iteration!r}"
            )
        super().__init__(
            latest_response=latest_response,
            max_iterations=max_iterations,
            current_iteration=current_iteration,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        latest_response: Any,
        max_iterations: int,
        current_iteration: int,
        **_: Any,
    ) -> bool:
        messages = self._coerce_messages(latest_response)
        for message in reversed(messages):
            if message.role == "assistant":
                if self._final_answer_marker in message.content:
                    return True
                break
        if current_iteration >= max_iterations:
            return True
        return False

    @staticmethod
    def _coerce_messages(latest_response: Any) -> tuple[AgentMessage, ...]:
        if isinstance(latest_response, AgentMessage):
            return (latest_response,)
        if isinstance(latest_response, (tuple, list)):
            collected: list[AgentMessage] = []
            for item in latest_response:
                if isinstance(item, AgentMessage):
                    collected.append(item)
            return tuple(collected)
        if hasattr(latest_response, "messages"):
            return tuple(
                m for m in latest_response.messages if isinstance(m, AgentMessage)
            )
        return ()
