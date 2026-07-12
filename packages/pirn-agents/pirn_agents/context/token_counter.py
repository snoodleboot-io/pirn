"""``TokenCounter`` — cached, provider-aware token counting for budgeting.

Wraps a pluggable :class:`~pirn_agents.context.token_estimator.TokenEstimator`
with a memoizing cache so repeated counting of the same text (the common case
while assembling and re-assembling context each turn) is O(1) after the first
estimate. Counting a sequence of :class:`AgentMessage` adds a small per-message
overhead to approximate the role/formatting tokens a chat wire format inserts
around each turn.
"""

from __future__ import annotations

from collections.abc import Sequence

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.context.token_estimator import TokenEstimator
from pirn_agents.types.agent_message import AgentMessage


class TokenCounter(PirnOpaqueValue):
    """A caching front-end over a provider :class:`TokenEstimator`.

    Subclasses :class:`PirnOpaqueValue` so a counter can flow through the knot
    graph as a resolved value (its mutable cache is treated as opaque, exactly
    like a stateful connector).
    """

    def __init__(self, *, estimator: TokenEstimator, per_message_overhead: int = 4) -> None:
        """Create a counter over ``estimator``.

        Args:
            estimator: The provider tokenization strategy to delegate to.
            per_message_overhead: Tokens added per message to approximate
                role/formatting overhead; must be non-negative.

        Raises:
            TypeError: If ``estimator`` is not a TokenEstimator.
            ValueError: If ``per_message_overhead`` is negative.
        """
        if not isinstance(estimator, TokenEstimator):
            raise TypeError(
                f"TokenCounter: estimator must be a TokenEstimator, got {type(estimator).__name__}"
            )
        if not isinstance(per_message_overhead, int) or per_message_overhead < 0:
            raise ValueError(
                "TokenCounter: per_message_overhead must be a non-negative int, "
                f"got {per_message_overhead!r}"
            )
        self._estimator = estimator
        self._per_message_overhead = per_message_overhead
        self._cache: dict[str, int] = {}
        self._hits = 0
        self._misses = 0

    @property
    def estimator(self) -> TokenEstimator:
        """Return the underlying provider estimator."""
        return self._estimator

    def count(self, text: str) -> int:
        """Return the cached token count for ``text``, estimating on a miss.

        Raises:
            TypeError: If ``text`` is not a str.
        """
        if not isinstance(text, str):
            raise TypeError(f"TokenCounter: text must be a str, got {type(text).__name__}")
        cached = self._cache.get(text)
        if cached is not None:
            self._hits += 1
            return cached
        self._misses += 1
        count = self._estimator.estimate(text)
        self._cache[text] = count
        return count

    def count_message(self, message: AgentMessage) -> int:
        """Return the token count of one message including per-message overhead.

        Raises:
            TypeError: If ``message`` is not an AgentMessage.
        """
        if not isinstance(message, AgentMessage):
            raise TypeError(
                f"TokenCounter: message must be an AgentMessage, got {type(message).__name__}"
            )
        return self.count(message.content) + self._per_message_overhead

    def count_messages(self, messages: Sequence[AgentMessage]) -> int:
        """Return the total token count across ``messages``.

        Raises:
            TypeError: If ``messages`` is not a sequence of AgentMessage.
        """
        if not isinstance(messages, Sequence) or isinstance(messages, (str, bytes)):
            raise TypeError(
                f"TokenCounter: messages must be a sequence, got {type(messages).__name__}"
            )
        return sum(self.count_message(message) for message in messages)

    def cache_info(self) -> dict[str, int]:
        """Return cache statistics: ``hits``, ``misses``, and ``size``."""
        return {"hits": self._hits, "misses": self._misses, "size": len(self._cache)}

    def clear_cache(self) -> None:
        """Drop all cached counts and reset the hit/miss counters."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0
