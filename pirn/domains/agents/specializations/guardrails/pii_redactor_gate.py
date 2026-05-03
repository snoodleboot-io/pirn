"""``PIIRedactorGate`` — standalone PII redactor for agent responses.

A :class:`SubTapestry` wrapping :class:`PIIResponseRedactor`. When
``patterns`` is ``None`` a sensible default of email, phone-number
and US SSN regexes is used. Returns the redacted
:class:`AgentResponse`.
"""

from __future__ import annotations

import re
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


class PIIRedactorGate(SubTapestry):
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
        patterns: Sequence[str] | None = None,
        **kwargs: Any,
    ) -> None:
        effective: tuple[str, ...]
        if patterns is None:
            effective = self._default_patterns
        else:
            collected: list[str] = []
            for index, raw in enumerate(patterns):
                if not isinstance(raw, str):
                    raise TypeError(
                        f"PIIRedactorGate: patterns[{index}] must be a "
                        f"string, got {type(raw).__name__}"
                    )
                re.compile(raw)
                collected.append(raw)
            effective = tuple(collected)
        self._patterns = effective
        super().__init__(response=response, _config=_config, **kwargs)

    async def process(
        self,
        response: AgentResponse,
        **_: Any,
    ) -> AgentResponse:
        """Redact PII matches from the response content using the configured patterns.

        Args:
            response: The agent response whose content is scanned for PII.

        Returns:
            An AgentResponse with PII redacted, or the original if no matches were found.

        Raises:
            RuntimeError: If the inner redactor does not return an AgentResponse.
        """
        with Tapestry() as inner:
            PIIResponseRedactor(
                response=response,
                patterns=self._patterns,
                _config=KnotConfig(id="redact"),
            )
        inner_result = await self._run_inner(inner)
        redacted = inner_result.outputs.get("redact")
        if not isinstance(redacted, AgentResponse):
            raise RuntimeError(
                "PIIRedactorGate: inner redactor did not return an "
                "AgentResponse"
            )
        return redacted
