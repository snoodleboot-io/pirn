"""``SafetyCheck`` — regex deny-list check on a message or response.

Algorithm:
    1. Receive the resolved message and ``deny_patterns`` sequence.
    2. Validate input types at process time.
    3. Compile each pattern string with ``re.IGNORECASE`` via ``compile_safe_pattern``.
    4. Search the message content against all compiled patterns.
    5. Return ``True`` (safe) if no pattern matches, ``False`` otherwise.


References:
    - :mod:`pirn_agents._regex_utils` — ``compile_safe_pattern``, ``search_any``
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents._regex_utils import compile_safe_pattern, search_any
from pirn_agents.types.agent_message import AgentMessage
from pirn_agents.types.agent_response import AgentResponse


class SafetyCheck(Knot):
    """Returns ``True`` when ``message.content`` matches no deny pattern.

    ``deny_patterns`` is a sequence of regex strings; a match against
    any of them flips the gate to ``False`` (not safe). Patterns are
    compiled at process time with ``re.IGNORECASE``. Both
    :class:`AgentMessage` and :class:`AgentResponse` are accepted on
    the input — anything else fails fast.
    """

    def __init__(
        self,
        *,
        message: Knot,
        deny_patterns: Knot | Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            message=message,
            deny_patterns=deny_patterns,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        message: AgentMessage | AgentResponse,
        deny_patterns: Sequence[str],
        **_: Any,
    ) -> bool:
        """Check the message body against deny-list patterns and return True if safe.

        Args:
            message: The agent message or response whose content is checked.
            deny_patterns: Regex strings that, when matched, indicate unsafe content.

        Returns:
            True if no deny pattern matches the content, False otherwise.

        Raises:
            TypeError: If message or patterns have wrong types.
            ValueError: If deny_patterns is empty or contains invalid patterns.
        """
        if not isinstance(message, (AgentMessage, AgentResponse)):
            raise TypeError(
                "SafetyCheck: message must be an AgentMessage or AgentResponse, "
                f"got {type(message).__name__}"
            )
        if not isinstance(deny_patterns, Sequence) or isinstance(deny_patterns, (str, bytes)):
            raise TypeError("SafetyCheck: deny_patterns must be a sequence of regex strings")
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
        content = message.content
        match = await search_any(tuple(compiled), content)
        return match is None
