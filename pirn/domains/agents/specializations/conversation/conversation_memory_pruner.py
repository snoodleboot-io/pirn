"""``ConversationMemoryPruner`` — prune conversation history to fit token budget.

Algorithm:
    1. Receive the resolved ``messages`` list and ``token_budget``.
    2. Validate input types at process time.
    3. Sum character lengths of all messages as a proxy for token count.
    4. While total > token_budget: remove the oldest non-system message.
    5. If no prunable message remains, stop (system messages are preserved).
    6. Return the pruned list.


References:
    - OpenAI documentation on managing conversation context windows.
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
        token_budget: Knot | int = 50,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(messages=messages, token_budget=token_budget, _config=_config, **kwargs)

    async def process(
        self,
        messages: Sequence[AgentMessage],
        token_budget: int = 50,
        **_: Any,
    ) -> list[AgentMessage]:
        """Prune oldest non-system messages until the history fits within token_budget.

        Args:
            messages: The full conversation message list, oldest first.
            token_budget: Maximum total character count allowed after pruning.

        Returns:
            A pruned list of AgentMessage objects that fits within the token budget,
            always preserving system messages.

        Raises:
            TypeError: If any element is not an AgentMessage instance.
            ValueError: If token_budget is not a positive int.
        """
        if not isinstance(token_budget, int) or token_budget <= 0:
            raise ValueError(
                "ConversationMemoryPruner: token_budget must be a positive "
                f"int, got {token_budget!r}"
            )
        for index, msg in enumerate(messages):
            if not isinstance(msg, AgentMessage):
                raise TypeError(
                    f"ConversationMemoryPruner: messages[{index}] must be an "
                    f"AgentMessage, got {type(msg).__name__}"
                )
        result = list(messages)
        while True:
            total = sum(len(msg.content) for msg in result)
            if total <= token_budget:
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
