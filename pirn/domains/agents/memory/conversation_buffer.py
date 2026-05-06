"""``ConversationBuffer`` — append a message to a rolling conversation window.

Algorithm:
    1. Receive the resolved ``new_message``, ``history``, and ``max_size``.
    2. Validate input types at process time.
    3. Append ``new_message`` to history.
    4. If the combined length exceeds ``max_size``, trim the oldest entries.
    5. Return the trimmed tuple.


References:
    - :class:`pirn.domains.agents.types.agent_message.AgentMessage`
"""

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
        max_size: Knot | int = 50,
        **kwargs: Any,
    ) -> None:
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
        """Append new_message to the history and return the trimmed conversation window.

        Args:
            new_message: The new message to append to the conversation history.
            history: The existing sequence of messages in the conversation.
            max_size: Maximum number of messages to keep; older entries are dropped.

        Returns:
            A tuple of the most recent messages up to max_size.

        Raises:
            TypeError: If new_message or history elements are not AgentMessage instances.
            ValueError: If max_size is not a positive int.
        """
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
        if not isinstance(max_size, int) or max_size <= 0:
            raise ValueError(
                "ConversationBuffer: max_size must be a positive int, "
                f"got {max_size!r}"
            )
        ordered = (*tuple(history), new_message)
        if len(ordered) <= max_size:
            return ordered
        return ordered[-max_size:]
