"""``SafetyCheck`` — regex deny-list check on a message or response.

Algorithm:
    1. Receive the resolved message and ``deny_patterns`` sequence.
    2. Validate input types at process time.
    3. Compile each pattern string with ``re.IGNORECASE`` via ``compile_safe_pattern``.
    4. Search the message content against all compiled patterns.
    5. Return ``True`` (safe) if no pattern matches, ``False`` otherwise.


References:
    - :mod:`pirn_agents._safe_pattern_compiler` — ``SafePatternCompiler``
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents._safe_pattern_compiler import SafePatternCompiler
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
        self._pattern_compiler = SafePatternCompiler()
        super().__init__(
            message=message,
            deny_patterns=deny_patterns,
            _config=_config,
            **kwargs,
        )
        # Validate concrete patterns up front so a bad deny-list fails fast at
        # build time. A ``Knot`` reference resolves later, so it is validated
        # at process time instead.
        if not isinstance(deny_patterns, Knot):
            self._pattern_compiler.compile_patterns(
                deny_patterns,
                owner="SafetyCheck",
                field="deny_patterns",
                flags=re.IGNORECASE,
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
        compiled = self._pattern_compiler.compile_patterns(
            deny_patterns,
            owner="SafetyCheck",
            field="deny_patterns",
            flags=re.IGNORECASE,
        )
        content = message.content
        match = await self._pattern_compiler.search_any(tuple(compiled), content)
        return match is None
