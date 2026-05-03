"""``ConversationMemoryPruner`` — prune conversation history to fit token budget.

A :class:`Knot` that removes the oldest non-system turns from a
conversation message list until the total character count (used as a
proxy for token count) fits within ``token_budget``. The system prompt
(any message with ``role == "system"``) is always preserved.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.types.agent_message import AgentMessage


class ConversationMemoryPruner(Knot):
    """Remove oldest non-system turns until history fits within token budget."""

    def __init__(
        self,
        *,
        messages: Knot | Sequence[AgentMessage],
        token_budget: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(token_budget, int) or token_budget <= 0:
            raise ValueError(
                "ConversationMemoryPruner: token_budget must be a positive "
                f"int, got {token_budget!r}"
            )
        self._token_budget = token_budget
        super().__init__(messages=messages, _config=_config, **kwargs)

    async def process(
        self,
        messages: Sequence[AgentMessage],
        **_: Any,
    ) -> list[AgentMessage]:
        """Prune oldest non-system messages until the history fits within token_budget.

        Args:
            messages: The full conversation message list, oldest first.

        Returns:
            A pruned list of AgentMessage objects that fits within the token budget,
            always preserving system messages.

        Raises:
            TypeError: If any element is not an AgentMessage instance.
        """
        for index, msg in enumerate(messages):
            if not isinstance(msg, AgentMessage):
                raise TypeError(
                    f"ConversationMemoryPruner: messages[{index}] must be an "
                    f"AgentMessage, got {type(msg).__name__}"
                )
        result = list(messages)
        while True:
            total = sum(len(msg.content) for msg in result)
            if total <= self._token_budget:
                break
            prunable_index = next(
                (
                    i
                    for i, msg in enumerate(result)
                    if msg.role != "system"
                ),
                None,
            )
            if prunable_index is None:
                break
            result.pop(prunable_index)
        return result
