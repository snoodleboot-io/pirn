"""``InputMessageScrubber`` — regex-based pre-prompt safety filter.

Inner stage knot used by :class:`InputGuardrailGate`. Walks each
incoming :class:`AgentMessage`, rejects any whose ``content`` matches
one of the deny patterns (raising :class:`ValueError`), and replaces
PII matches with ``"<redacted>"`` literal substitutes. Returns the
cleaned tuple of messages.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents._regex_utils import compile_safe_pattern
from pirn.domains.agents.types.agent_message import AgentMessage


class InputMessageScrubber(Knot):
    """Validates and PII-scrubs a tuple of :class:`AgentMessage`."""

    def __init__(
        self,
        *,
        messages: Knot | Sequence[AgentMessage],
        deny_patterns: Sequence[str],
        pii_patterns: Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        deny_compiled: list[re.Pattern[str]] = []
        for index, raw in enumerate(deny_patterns):
            if not isinstance(raw, str):
                raise TypeError(
                    f"InputMessageScrubber: deny_patterns[{index}] must be a "
                    f"string, got {type(raw).__name__}"
                )
            deny_compiled.append(
                compile_safe_pattern(raw, index=index, owner="InputMessageScrubber", field="deny_patterns")
            )
        pii_compiled: list[re.Pattern[str]] = []
        for index, raw in enumerate(pii_patterns):
            if not isinstance(raw, str):
                raise TypeError(
                    f"InputMessageScrubber: pii_patterns[{index}] must be a "
                    f"string, got {type(raw).__name__}"
                )
            pii_compiled.append(
                compile_safe_pattern(raw, index=index, owner="InputMessageScrubber", field="pii_patterns")
            )
        self._deny_compiled = tuple(deny_compiled)
        self._pii_compiled = tuple(pii_compiled)
        super().__init__(messages=messages, _config=_config, **kwargs)

    async def process(
        self,
        messages: Sequence[AgentMessage],
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
        cleaned: list[AgentMessage] = []
        for index, message in enumerate(messages):
            if not isinstance(message, AgentMessage):
                raise TypeError(
                    f"InputMessageScrubber: messages[{index}] must be an "
                    f"AgentMessage, got {type(message).__name__}"
                )
            content = message.content

            def _check_deny(c: str = content) -> re.Pattern[str] | None:
                for p in self._deny_compiled:
                    if p.search(c):
                        return p
                return None

            denied = await asyncio.to_thread(_check_deny)
            if denied is not None:
                raise ValueError(
                    f"InputMessageScrubber: messages[{index}] matched "
                    f"deny pattern {denied.pattern!r}"
                )

            def _apply_pii(c: str = content) -> str:
                for p in self._pii_compiled:
                    c = p.sub("<redacted>", c)
                return c

            redacted_content = await asyncio.to_thread(_apply_pii)
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
