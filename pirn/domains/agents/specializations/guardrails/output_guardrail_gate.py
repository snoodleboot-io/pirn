"""``OutputGuardrailGate`` — post-LLM safety gate.

A :class:`SubTapestry` wrapping :class:`OutputResponseValidator`.
Scans :class:`AgentResponse.content` for deny patterns and ensures
every ``tool_calls`` entry refers to a tool in
``allowed_tool_names``. Returns the validated response unchanged on
success and raises :class:`ValueError` (surfaced as a failed run) on
any rule violation.

Algorithm:
    1. Run an inner :class:`Tapestry` containing a single
       :class:`OutputResponseValidator` with ``deny_patterns`` and
       ``allowed_tool_names`` forwarded from the caller.
    2. The validator checks each compiled deny pattern against
       ``response.content`` and each ``tool_calls`` entry against
       ``allowed_tool_names``, raising :class:`ValueError` on any violation.
    3. Extract the validated :class:`AgentResponse` from the inner result and
       return it unchanged.


References:
    - pirn-native: :class:`pirn.domains.agents.specializations.guardrails.output_response_validator.OutputResponseValidator`
    - pirn-native: :class:`pirn.domains.agents.types.agent_response.AgentResponse`
"""

from __future__ import annotations

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
        """Validate the response against deny patterns and allowed tool names, returning it unchanged on success.

        Args:
            response: The agent response to validate.

        Returns:
            The original AgentResponse if all checks pass.

        Raises:
            RuntimeError: If the inner validator does not return an AgentResponse.
        """
        with Tapestry() as inner:
            OutputResponseValidator(
                response=response,
                deny_patterns=tuple(deny_patterns),
                allowed_tool_names=tuple(allowed_tool_names),
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
