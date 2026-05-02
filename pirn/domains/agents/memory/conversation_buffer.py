"""``ConversationBuffer`` — append a message to a rolling conversation window."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.types.agent_message import AgentMessage


class ConversationBuffer(Knot):
    """Appends ``new_message`` to the conversation, trimming to ``max_size``.

    Acts as the agent's short-term memory window: the most recent
    ``max_size`` messages are kept; older entries roll off.
    """

    def __init__(
        self,
        *,
        new_message: Knot,
        _config: KnotConfig,
        history: Knot | Sequence[AgentMessage] = (),
        max_size: int = 50,
        **kwargs: Any,
    ) -> None:
        if not isinstance(max_size, int) or max_size <= 0:
            raise ValueError(
                "ConversationBuffer: max_size must be a positive int, "
                f"got {max_size!r}"
            )
        super().__init__(
            new_message=new_message,
            history=history,
            max_size=max_size,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        new_message: AgentMessage,
        history: Sequence[AgentMessage],
        max_size: int,
        **_: Any,
    ) -> tuple[AgentMessage, ...]:
        if not isinstance(new_message, AgentMessage):
            raise TypeError(
                "ConversationBuffer: new_message must be an AgentMessage, "
                f"got {type(new_message).__name__}"
            )
        if not isinstance(history, Sequence) or isinstance(history, (str, bytes)):
            raise TypeError(
                "ConversationBuffer: history must be a sequence of AgentMessage, "
                f"got {type(history).__name__}"
            )
        for index, message in enumerate(history):
            if not isinstance(message, AgentMessage):
                raise TypeError(
                    f"ConversationBuffer: history[{index}] must be an "
                    f"AgentMessage, got {type(message).__name__}"
                )
        ordered = (*tuple(history), new_message)
        if len(ordered) <= max_size:
            return ordered
        return ordered[-max_size:]
