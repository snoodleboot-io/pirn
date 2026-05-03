"""``MultiTurnContextAssembler`` — assemble a windowed message list for LLM input.

A :class:`Knot` that takes a sequence of :class:`AgentMessage` objects
representing recent conversation turns and returns a windowed list of
role/content dicts suitable for passing directly to an LLM. The window
respects ``max_turns`` (number of messages) and ``max_tokens``
(approximate token budget; each character counts as one token for
budget purposes).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.types.agent_message import AgentMessage


class MultiTurnContextAssembler(Knot):
    """Assemble a windowed message list from recent conversation turns."""

    def __init__(
        self,
        *,
        messages: Knot | Sequence[AgentMessage],
        max_turns: int,
        max_tokens: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(max_turns, int) or max_turns <= 0:
            raise ValueError(
                "MultiTurnContextAssembler: max_turns must be a positive int, "
                f"got {max_turns!r}"
            )
        if not isinstance(max_tokens, int) or max_tokens <= 0:
            raise ValueError(
                "MultiTurnContextAssembler: max_tokens must be a positive int, "
                f"got {max_tokens!r}"
            )
        self._max_turns = max_turns
        self._max_tokens = max_tokens
        super().__init__(messages=messages, _config=_config, **kwargs)

    async def process(
        self,
        messages: Sequence[AgentMessage],
        **_: Any,
    ) -> list[dict[str, str]]:
        """Assemble a windowed message list from the conversation history.

        Args:
            messages: The full sequence of conversation messages, oldest first.

        Returns:
            A list of role/content dicts for the most recent window of turns,
            respecting max_turns and max_tokens limits.

        Raises:
            TypeError: If any element is not an AgentMessage instance.
        """
        for index, msg in enumerate(messages):
            if not isinstance(msg, AgentMessage):
                raise TypeError(
                    f"MultiTurnContextAssembler: messages[{index}] must be an "
                    f"AgentMessage, got {type(msg).__name__}"
                )
        recent = list(messages)[-self._max_turns :]
        window: list[dict[str, str]] = []
        budget = self._max_tokens
        for msg in reversed(recent):
            cost = len(msg.content)
            if budget - cost < 0:
                break
            budget -= cost
            window.append({"role": msg.role, "content": msg.content})
        window.reverse()
        return window
