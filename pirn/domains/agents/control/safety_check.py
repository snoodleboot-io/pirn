"""``SafetyCheck`` — regex deny-list check on a message or response."""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents._regex_utils import compile_safe_pattern, search_any
from pirn.domains.agents.types.agent_message import AgentMessage
from pirn.domains.agents.types.agent_response import AgentResponse


class SafetyCheck(Knot):
    """Returns ``True`` when ``message.content`` matches no deny pattern.

    ``deny_patterns`` is a sequence of regex strings; a match against
    any of them flips the gate to ``False`` (not safe). Patterns are
    compiled at construction with ``re.IGNORECASE``. Both
    :class:`AgentMessage` and :class:`AgentResponse` are accepted on
    the input — anything else fails fast.
    """

    def __init__(
        self,
        *,
        message: Knot,
        deny_patterns: Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(deny_patterns, Sequence) or isinstance(
            deny_patterns, (str, bytes)
        ):
            raise TypeError(
                "SafetyCheck: deny_patterns must be a sequence of regex strings"
            )
        if not deny_patterns:
            raise ValueError("SafetyCheck: deny_patterns must be non-empty")
        compiled: list[re.Pattern[str]] = []
        for index, pattern in enumerate(deny_patterns):
            if not isinstance(pattern, str) or not pattern:
                raise ValueError(
                    f"SafetyCheck: deny_patterns[{index}] must be a non-empty "
                    f"string, got {pattern!r}"
                )
            compiled.append(
                compile_safe_pattern(
                    pattern,
                    index=index,
                    owner="SafetyCheck",
                    field="deny_patterns",
                    flags=re.IGNORECASE,
                )
            )
        super().__init__(
            message=message,
            deny_patterns=tuple(deny_patterns),
            _config=_config,
            **kwargs,
        )
        self._mutable_compiled = tuple(compiled)

    async def process(
        self,
        message: AgentMessage | AgentResponse,
        deny_patterns: tuple[str, ...],
        **_: Any,
    ) -> bool:
        """Check the message body against deny-list patterns and return True if safe.

        Args:
            message: The agent message or response whose content is checked.
            deny_patterns: Compiled regex patterns that, when matched, indicate unsafe content.

        Returns:
            True if no deny pattern matches the content, False otherwise.

        Raises:
            TypeError: If message is not an AgentMessage or AgentResponse instance.
        """
        if not isinstance(message, (AgentMessage, AgentResponse)):
            raise TypeError(
                "SafetyCheck: message must be an AgentMessage or AgentResponse, "
                f"got {type(message).__name__}"
            )
        del deny_patterns  # consumed at construction; compiled patterns used here
        content = message.content
        match = await search_any(self._mutable_compiled, content)
        return match is None
