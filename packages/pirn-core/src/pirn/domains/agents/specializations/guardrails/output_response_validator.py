"""``OutputResponseValidator`` — post-LLM safety filter on a response.

Inner stage knot used by :class:`OutputGuardrailGate`. Rejects the
response when its ``content`` matches any deny pattern, or when any
of its ``tool_calls`` references a tool name not in the allow list.
On success the response is returned unchanged.

Algorithm:
    1. Compile each raw string in ``deny_patterns`` into a regex via
       :func:`compile_safe_pattern`; raise :class:`ValueError` on invalid
       patterns.
    2. Build a frozen set from ``allowed_tool_names`` for O(1) membership
       tests.
    3. Validate that ``response`` is an :class:`AgentResponse`; raise
       :class:`TypeError` otherwise.
    4. Run :func:`search_any` over the compiled deny patterns against
       ``response.content``; raise :class:`ValueError` on the first match.
    5. Iterate ``response.tool_calls``; raise :class:`ValueError` for any
       ``tool_name`` absent from the allowed set.
    6. Return the response unchanged when all checks pass.


References:
    - pirn-native: :class:`pirn.domains.agents.types.agent_response.AgentResponse`
    - pirn-native: :func:`pirn.domains.agents._regex_utils.compile_safe_pattern`
    - pirn-native: :func:`pirn.domains.agents._regex_utils.search_any`
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents._regex_utils import compile_safe_pattern, search_any
from pirn.domains.agents.types.agent_response import AgentResponse


class OutputResponseValidator(Knot):
    """Validates an :class:`AgentResponse` against deny + allow rules."""

    def __init__(
        self,
        *,
        response: Knot | AgentResponse,
        deny_patterns: Knot | Sequence[str],
        allowed_tool_names: Knot | Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            response=response,
            deny_patterns=deny_patterns,
            allowed_tool_names=allowed_tool_names,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        response: AgentResponse,
        deny_patterns: Sequence[str] = (),
        allowed_tool_names: Sequence[str] = (),
        **_: Any,
    ) -> AgentResponse:
        """Reject the response if it matches any deny pattern or references a disallowed tool; return it unchanged otherwise.

        Args:
            response: The agent response to validate.

        Returns:
            The original AgentResponse if all checks pass.

        Raises:
            TypeError: If response is not an AgentResponse instance.
            ValueError: If the response content matches a deny pattern or a tool call references a disallowed tool.
        """
        deny_compiled = tuple(
            compile_safe_pattern(
                raw, index=i, owner="OutputResponseValidator", field="deny_patterns"
            )
            for i, raw in enumerate(deny_patterns)
        )
        allowed_set = frozenset(allowed_tool_names)
        if not isinstance(response, AgentResponse):
            raise TypeError(
                "OutputResponseValidator: response must be an AgentResponse, "
                f"got {type(response).__name__}"
            )
        match = await search_any(deny_compiled, response.content)
        if match is not None:
            raise ValueError(
                "OutputResponseValidator: response content matched deny "
                f"pattern {match.re.pattern!r}"
            )
        for index, call in enumerate(response.tool_calls):
            if call.tool_name not in allowed_set:
                raise ValueError(
                    "OutputResponseValidator: tool_calls"
                    f"[{index}] references disallowed tool "
                    f"{call.tool_name!r}"
                )
        return response
