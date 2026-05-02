"""``OutputGuardrailGate`` — post-LLM safety gate.

A :class:`SubTapestry` wrapping :class:`OutputResponseValidator`.
Scans :class:`AgentResponse.content` for deny patterns and ensures
every ``tool_calls`` entry refers to a tool in
``allowed_tool_names``. Returns the validated response unchanged on
success and raises :class:`ValueError` (surfaced as a failed run) on
any rule violation.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.specializations.guardrails.output_response_validator import (
    OutputResponseValidator,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class OutputGuardrailGate(SubTapestry):
    """Post-LLM deny + tool-allowlist gate over an :class:`AgentResponse`."""

    def __init__(
        self,
        *,
        response: Knot | AgentResponse,
        deny_patterns: Sequence[str],
        allowed_tool_names: Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        for index, raw in enumerate(deny_patterns):
            if not isinstance(raw, str):
                raise TypeError(
                    f"OutputGuardrailGate: deny_patterns[{index}] must be a "
                    f"string, got {type(raw).__name__}"
                )
            re.compile(raw)
        for index, name in enumerate(allowed_tool_names):
            if not isinstance(name, str):
                raise TypeError(
                    f"OutputGuardrailGate: allowed_tool_names[{index}] must "
                    f"be a string, got {type(name).__name__}"
                )
        self._deny_patterns = tuple(deny_patterns)
        self._allowed_tool_names = tuple(allowed_tool_names)
        super().__init__(response=response, _config=_config, **kwargs)

    async def process(
        self,
        response: AgentResponse,
        **_: Any,
    ) -> AgentResponse:
        with Tapestry() as inner:
            OutputResponseValidator(
                response=response,
                deny_patterns=self._deny_patterns,
                allowed_tool_names=self._allowed_tool_names,
                _config=KnotConfig(id="validate"),
            )
        inner_result = await self._run_inner(inner)
        validated = inner_result.outputs.get("validate")
        if not isinstance(validated, AgentResponse):
            raise RuntimeError(
                "OutputGuardrailGate: inner validator did not return an "
                "AgentResponse"
            )
        return validated
