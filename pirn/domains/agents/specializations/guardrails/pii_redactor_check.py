"""``PiiRedactorCheck`` — standalone PII redactor for agent responses.

A :class:`SubTapestry` wrapping :class:`PIIResponseRedactor`. When
``patterns`` is ``None`` a sensible default of email, phone-number
and US SSN regexes is used. Returns the redacted
:class:`AgentResponse`.

Algorithm:
    1. If ``patterns`` is ``None``, fall back to the built-in default
       tuple of email, US SSN, and phone-number regexes.
    2. Build an inner :class:`Tapestry` containing a single
       :class:`PIIResponseRedactor` node wired to ``response`` and the
       effective pattern list.
    3. Execute the inner tapestry via :meth:`_run_inner`.
    4. Extract the output keyed ``"redact"`` from the inner result;
       raise :class:`RuntimeError` if it is not an
       :class:`AgentResponse`.
    5. Return the redacted :class:`AgentResponse`.


References:
    - pirn-native: :class:`pirn.domains.agents.specializations.guardrails.pii_response_redactor.PIIResponseRedactor`
    - pirn-native: :class:`pirn.domains.agents.types.agent_response.AgentResponse`
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.specializations.guardrails.pii_response_redactor import (
    PIIResponseRedactor,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class PiiRedactorCheck(SubTapestry):
    """Standalone PII redactor for use after the LLM call."""

    _default_patterns: tuple[str, ...] = (
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        r"\b\d{3}-\d{2}-\d{4}\b",
        r"\b(?:\+?1[-. ]?)?(?:\(\d{3}\)|\d{3})[-. ]?\d{3}[-. ]?\d{4}\b",
    )

    def __init__(
        self,
        *,
        response: Knot | AgentResponse,
        _config: KnotConfig,
        patterns: Knot | Sequence[str] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(response=response, patterns=patterns, _config=_config, **kwargs)

    async def process(
        self,
        response: AgentResponse,
        patterns: Sequence[str] | None = None,
        **_: Any,
    ) -> AgentResponse:
        """Redact PII matches from the response content using the configured patterns.

        Args:
            response: The agent response whose content is scanned for PII.
            patterns: Optional sequence of regex patterns to match PII. When
                ``None`` the built-in defaults (email, SSN, phone) are used.

        Returns:
            An AgentResponse with PII redacted, or the original if no matches were found.

        Raises:
            RuntimeError: If the inner redactor does not return an AgentResponse.
        """
        effective = self._default_patterns if patterns is None else tuple(patterns)
        with Tapestry() as inner:
            PIIResponseRedactor(
                response=response,
                patterns=effective,
                _config=KnotConfig(id="redact"),
            )
        inner_result = await self._run_inner(inner)
        redacted = inner_result.outputs.get("redact")
        if not isinstance(redacted, AgentResponse):
            raise RuntimeError(
                "PiiRedactorCheck: inner redactor did not return an "
                "AgentResponse"
            )
        return redacted
