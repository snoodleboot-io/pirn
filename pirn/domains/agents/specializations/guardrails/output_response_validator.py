"""``OutputResponseValidator`` — post-LLM safety filter on a response.

Inner stage knot used by :class:`OutputGuardrailGate`. Rejects the
response when its ``content`` matches any deny pattern, or when any
of its ``tool_calls`` references a tool name not in the allow list.
On success the response is returned unchanged.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.types.agent_response import AgentResponse


class OutputResponseValidator(Knot):
    """Validates an :class:`AgentResponse` against deny + allow rules."""

    def __init__(
        self,
        *,
        response: Knot | AgentResponse,
        deny_patterns: Sequence[str],
        allowed_tool_names: Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        deny_compiled: list[re.Pattern[str]] = []
        for index, raw in enumerate(deny_patterns):
            if not isinstance(raw, str):
                raise TypeError(
                    f"OutputResponseValidator: deny_patterns[{index}] must be "
                    f"a string, got {type(raw).__name__}"
                )
            deny_compiled.append(re.compile(raw))
        for index, name in enumerate(allowed_tool_names):
            if not isinstance(name, str):
                raise TypeError(
                    f"OutputResponseValidator: allowed_tool_names[{index}] "
                    f"must be a string, got {type(name).__name__}"
                )
        self._deny_compiled = tuple(deny_compiled)
        self._allowed_tool_names = frozenset(allowed_tool_names)
        super().__init__(response=response, _config=_config, **kwargs)

    async def process(
        self,
        response: AgentResponse,
        **_: Any,
    ) -> AgentResponse:
        if not isinstance(response, AgentResponse):
            raise TypeError(
                "OutputResponseValidator: response must be an AgentResponse, "
                f"got {type(response).__name__}"
            )
        for pattern in self._deny_compiled:
            if pattern.search(response.content):
                raise ValueError(
                    "OutputResponseValidator: response content matched deny "
                    f"pattern {pattern.pattern!r}"
                )
        for index, call in enumerate(response.tool_calls):
            if call.tool_name not in self._allowed_tool_names:
                raise ValueError(
                    "OutputResponseValidator: tool_calls"
                    f"[{index}] references disallowed tool "
                    f"{call.tool_name!r}"
                )
        return response
