"""``MultiTurnContextAssembler`` — assemble a windowed message list for LLM input.

Algorithm:
    1. Receive the resolved ``messages``, ``max_turns``, and ``max_tokens``.
    2. Validate input types at process time.
    3. Slice the last ``max_turns`` messages.
    4. Iterate in reverse, accumulating messages until ``max_tokens`` is exhausted.
    5. Reverse the accumulated window and return as role/content dicts.


References:
    - Standard sliding-window context truncation for LLM APIs.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.types.agent_message import AgentMessage


class MultiTurnContextAssembler(Knot):
    """Assemble a windowed message list from recent conversation turns."""

    def __init__(
        self,
        *,
        messages: Knot | Sequence[AgentMessage],
        max_turns: Knot | int = 10,
        max_tokens: Knot | int = 4000,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            messages=messages,
            max_turns=max_turns,
            max_tokens=max_tokens,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        messages: Sequence[AgentMessage],
        max_turns: int = 10,
        max_tokens: int = 4000,
        **_: Any,
    ) -> list[dict[str, str]]:
        """Assemble a windowed message list from the conversation history.

        Args:
            messages: The full sequence of conversation messages, oldest first.
            max_turns: Maximum number of messages to include in the window.
            max_tokens: Approximate token budget; each character counts as one token.

        Returns:
            A list of role/content dicts for the most recent window of turns,
            respecting max_turns and max_tokens limits.

        Raises:
            TypeError: If any element is not an AgentMessage instance.
            ValueError: If max_turns or max_tokens are not positive ints.
        """
        if not isinstance(max_turns, int) or max_turns <= 0:
            raise ValueError(
                f"MultiTurnContextAssembler: max_turns must be a positive int, got {max_turns!r}"
            )
        if not isinstance(max_tokens, int) or max_tokens <= 0:
            raise ValueError(
                f"MultiTurnContextAssembler: max_tokens must be a positive int, got {max_tokens!r}"
            )
        for index, msg in enumerate(messages):
            if not isinstance(msg, AgentMessage):
                raise TypeError(
                    f"MultiTurnContextAssembler: messages[{index}] must be an "
                    f"AgentMessage, got {type(msg).__name__}"
                )
        recent = list(messages)[-max_turns:]
        window: list[dict[str, str]] = []
        budget = max_tokens
        for msg in reversed(recent):
            cost = len(msg.content)
            if budget - cost < 0:
                break
            budget -= cost
            window.append({"role": msg.role, "content": msg.content})
        window.reverse()
        return window
