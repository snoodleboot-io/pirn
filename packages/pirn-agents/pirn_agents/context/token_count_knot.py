"""``TokenCountKnot`` — count the tokens of a message sequence in the graph.

Algorithm:
    1. Receive the resolved ``counter`` and ``messages``.
    2. Validate input types at process time.
    3. Delegate to :meth:`TokenCounter.count_messages`.
    4. Return the total token count.


References:
    - :class:`pirn_agents.context.token_counter.TokenCounter`
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.context.token_counter import TokenCounter
from pirn_agents.types.agent_message import AgentMessage


class TokenCountKnot(Knot):
    """Counts the tokens of a message sequence via an injected counter."""

    def __init__(
        self,
        *,
        counter: Knot | TokenCounter,
        messages: Knot | Sequence[AgentMessage],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            counter=counter,
            messages=messages,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        counter: TokenCounter,
        messages: Sequence[AgentMessage],
        **_: Any,
    ) -> int:
        """Return the total token count of ``messages`` using ``counter``.

        Args:
            counter: The token counter to delegate to.
            messages: The messages to count.

        Returns:
            The total token count including per-message overhead.

        Raises:
            TypeError: If ``counter`` is not a TokenCounter.
        """
        if not isinstance(counter, TokenCounter):
            raise TypeError(
                f"TokenCountKnot: counter must be a TokenCounter, got {type(counter).__name__}"
            )
        return counter.count_messages(messages)
