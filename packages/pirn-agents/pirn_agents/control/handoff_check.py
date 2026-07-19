"""``HandoffCheck`` — detect responses that should escalate to a human/another agent.

Algorithm:
    1. Receive the resolved ``AgentResponse`` and the ``escalation_patterns`` sequence.
    2. Validate input types at process time.
    3. Compile each pattern string with ``re.IGNORECASE`` via ``compile_safe_pattern``.
    4. Search the response content against all compiled patterns in sequence.
    5. Return ``True`` if any pattern matches, ``False`` otherwise.


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
from pirn_agents.types.agent_response import AgentResponse


class HandoffCheck(Knot):
    """Returns ``True`` when the response matches an escalation pattern.

    ``escalation_patterns`` is a sequence of regex strings; a match
    against any of them flips the gate to ``True``. Patterns are
    compiled at process time with ``re.IGNORECASE``.
    """

    def __init__(
        self,
        *,
        response: Knot,
        escalation_patterns: Knot | Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        self._pattern_compiler = SafePatternCompiler()
        super().__init__(
            response=response,
            escalation_patterns=escalation_patterns,
            _config=_config,
            **kwargs,
        )
        # Validate concrete patterns up front so a bad escalation-list fails
        # fast at build time. A ``Knot`` reference resolves later, so it is
        # validated at process time instead.
        if not isinstance(escalation_patterns, Knot):
            self._pattern_compiler.compile_patterns(
                escalation_patterns,
                owner="HandoffCheck",
                field="escalation_patterns",
                flags=re.IGNORECASE,
            )

    async def process(
        self,
        response: AgentResponse,
        escalation_patterns: Sequence[str],
        **_: Any,
    ) -> bool:
        """Check the response content against escalation patterns and return True if any match.

        Args:
            response: The agent response whose content is searched for escalation patterns.
            escalation_patterns: Regex strings checked against the response content.

        Returns:
            True if the response content matches any escalation pattern, False otherwise.

        Raises:
            TypeError: If response is not an AgentResponse or patterns is not a sequence.
            ValueError: If escalation_patterns is empty or contains invalid patterns.
        """
        if not isinstance(response, AgentResponse):
            raise TypeError(
                f"HandoffCheck: response must be an AgentResponse, got {type(response).__name__}"
            )
        compiled = self._pattern_compiler.compile_patterns(
            escalation_patterns,
            owner="HandoffCheck",
            field="escalation_patterns",
            flags=re.IGNORECASE,
        )
        match = await self._pattern_compiler.search_any(tuple(compiled), response.content)
        return match is not None
