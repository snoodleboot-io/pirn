"""``HandoffCheck`` — detect responses that should escalate to a human/another agent."""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.types.agent_response import AgentResponse


class HandoffCheck(Knot):
    """Returns ``True`` when the response matches an escalation pattern.

    ``escalation_patterns`` is a sequence of regex strings; a match
    against any of them flips the gate to ``True``. Patterns are
    compiled at construction with ``re.IGNORECASE``.
    """

    def __init__(
        self,
        *,
        response: Knot,
        escalation_patterns: Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(escalation_patterns, Sequence) or isinstance(
            escalation_patterns, (str, bytes)
        ):
            raise TypeError(
                "HandoffCheck: escalation_patterns must be a sequence of regex strings"
            )
        if not escalation_patterns:
            raise ValueError(
                "HandoffCheck: escalation_patterns must be non-empty"
            )
        compiled: list[re.Pattern[str]] = []
        for index, pattern in enumerate(escalation_patterns):
            if not isinstance(pattern, str) or not pattern:
                raise ValueError(
                    f"HandoffCheck: escalation_patterns[{index}] must be a "
                    f"non-empty string, got {pattern!r}"
                )
            try:
                compiled.append(re.compile(pattern, flags=re.IGNORECASE))
            except re.error as exc:
                raise ValueError(
                    f"HandoffCheck: escalation_patterns[{index}] is not a "
                    f"valid regex: {exc}"
                ) from exc
        super().__init__(
            response=response,
            escalation_patterns=tuple(escalation_patterns),
            _config=_config,
            **kwargs,
        )
        self._mutable_compiled = tuple(compiled)

    async def process(
        self,
        response: AgentResponse,
        escalation_patterns: tuple[str, ...],
        **_: Any,
    ) -> bool:
        """Check the response content against escalation patterns and return True if any match.

        Args:
            response: The agent response whose content is searched for escalation patterns.
            escalation_patterns: Compiled regex patterns checked against the response content.

        Returns:
            True if the response content matches any escalation pattern, False otherwise.

        Raises:
            TypeError: If response is not an AgentResponse instance.
        """
        if not isinstance(response, AgentResponse):
            raise TypeError(
                "HandoffCheck: response must be an AgentResponse, "
                f"got {type(response).__name__}"
            )
        del escalation_patterns
        for pattern in self._mutable_compiled:
            if pattern.search(response.content):
                return True
        return False
