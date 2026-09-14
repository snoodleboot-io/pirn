"""``InputMessageScrubber`` — regex-based pre-prompt safety filter.

Inner stage knot used by :class:`InputGuardrailCheck`. Walks each
incoming :class:`AgentMessage`, rejects any whose ``content`` matches
one of the deny patterns (raising :class:`ValueError`), and replaces
PII matches with ``"<redacted>"`` literal substitutes. Returns the
cleaned tuple of messages.

Algorithm:
    1. Compile all ``deny_patterns`` and ``pii_patterns`` strings via
       :meth:`SafePatternCompiler.compile_safe_pattern`.
    2. Iterate over ``messages`` in order:
       a. Raise :class:`TypeError` if an element is not an :class:`AgentMessage`.
       b. Run deny-pattern matching in a thread (``asyncio.to_thread``) and
          raise :class:`ValueError` if any pattern matches the message content.
       c. Apply PII substitution in a thread, replacing each match with the
          literal string ``"<redacted>"``.
    3. Construct a new :class:`AgentMessage` for each input with the redacted
       content and all other fields (``role``, ``name``, ``tool_call_id``,
       ``created_at``) preserved.
    4. Return the collected messages as an immutable ``tuple``.


References:
    - pirn-native: :class:`pirn_agents.types.messaging.agent_message.AgentMessage`
    - Python stdlib: :mod:`asyncio` (``to_thread``)
    - Python stdlib: :mod:`re`
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Sequence
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.security._safe_pattern_compiler import SafePatternCompiler
from pirn_agents.types.messaging.agent_message import AgentMessage


class InputMessageScrubber(Knot):
    """Validates and PII-scrubs a tuple of :class:`AgentMessage`."""

    #: Stateless helper shared across instances (Knot Rule 4 — class-level constant).
    _pattern_compiler: ClassVar[SafePatternCompiler] = SafePatternCompiler()

    def __init__(
        self,
        *,
        messages: Knot | Sequence[AgentMessage],
        deny_patterns: Knot | Sequence[str],
        pii_patterns: Knot | Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            messages=messages,
            deny_patterns=deny_patterns,
            pii_patterns=pii_patterns,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        messages: Sequence[AgentMessage],
        deny_patterns: Sequence[str] = (),
        pii_patterns: Sequence[str] = (),
        **_: Any,
    ) -> tuple[AgentMessage, ...]:
        """Validate each message against deny patterns and redact PII matches, returning cleaned messages.

        Args:
            messages: The sequence of agent messages to validate and redact.

        Returns:
            A tuple of AgentMessage instances with PII redacted and deny patterns checked.

        Raises:
            TypeError: If any element of messages is not an AgentMessage.
            ValueError: If any message content matches a deny pattern.
        """
        deny_compiled = tuple(
            self._pattern_compiler.compile_safe_pattern(
                raw, index=i, owner="InputMessageScrubber", field="deny_patterns"
            )
            for i, raw in enumerate(deny_patterns)
        )
        pii_compiled = tuple(
            self._pattern_compiler.compile_safe_pattern(
                raw, index=i, owner="InputMessageScrubber", field="pii_patterns"
            )
            for i, raw in enumerate(pii_patterns)
        )
        cleaned: list[AgentMessage] = []
        for index, message in enumerate(messages):
            if not isinstance(message, AgentMessage):
                raise TypeError(
                    f"InputMessageScrubber: messages[{index}] must be an "
                    f"AgentMessage, got {type(message).__name__}"
                )
            content = message.content
            denied = await asyncio.to_thread(
                InputMessageScrubber._first_deny_match, deny_compiled, content
            )
            if denied is not None:
                raise ValueError(
                    f"InputMessageScrubber: messages[{index}] matched "
                    f"deny pattern {denied.pattern!r}"
                )

            redacted_content = await asyncio.to_thread(
                InputMessageScrubber._redact_pii, pii_compiled, content
            )
            cleaned.append(
                AgentMessage(
                    role=message.role,
                    content=redacted_content,
                    name=message.name,
                    tool_call_id=message.tool_call_id,
                    created_at=message.created_at,
                )
            )
        return tuple(cleaned)

    @staticmethod
    def _first_deny_match(
        patterns: Sequence[re.Pattern[str]], content: str
    ) -> re.Pattern[str] | None:
        """Return the first deny pattern ``content`` matches, or ``None``."""
        for pattern in patterns:
            if pattern.search(content):
                return pattern
        return None

    @staticmethod
    def _redact_pii(patterns: Sequence[re.Pattern[str]], content: str) -> str:
        """Replace every PII pattern match in ``content`` with ``<redacted>``."""
        for pattern in patterns:
            content = pattern.sub("<redacted>", content)
        return content
