"""``PIIResponseRedactor`` — regex-driven PII redaction over a response.

Inner stage knot used by :class:`PIIRedactorGate`. Walks each compiled
PII pattern against the supplied :class:`AgentResponse.content` and
replaces matches with the literal ``"<redacted>"``. Returns a new
:class:`AgentResponse` with the redacted content; ``tool_calls``,
``finish_reason`` and ``usage`` are forwarded unchanged.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.types.agent_response import AgentResponse


class PIIResponseRedactor(Knot):
    """Redacts PII matches in :class:`AgentResponse.content`."""

    def __init__(
        self,
        *,
        response: Knot | AgentResponse,
        patterns: Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        compiled: list[re.Pattern[str]] = []
        for index, raw in enumerate(patterns):
            if not isinstance(raw, str):
                raise TypeError(
                    f"PIIResponseRedactor: patterns[{index}] must be a "
                    f"string, got {type(raw).__name__}"
                )
            compiled.append(re.compile(raw))
        self._compiled = tuple(compiled)
        super().__init__(response=response, _config=_config, **kwargs)

    async def process(
        self,
        response: AgentResponse,
        **_: Any,
    ) -> AgentResponse:
        """Replace PII matches in the response content with '<redacted>' and return the cleaned response.

        Args:
            response: The agent response whose content is scanned and redacted.

        Returns:
            A new AgentResponse with PII replaced, or the original if no patterns matched.

        Raises:
            TypeError: If response is not an AgentResponse instance.
        """
        if not isinstance(response, AgentResponse):
            raise TypeError(
                "PIIResponseRedactor: response must be an AgentResponse, "
                f"got {type(response).__name__}"
            )
        redacted = response.content
        for pattern in self._compiled:
            redacted = pattern.sub("<redacted>", redacted)
        if redacted == response.content:
            return response
        return AgentResponse(
            content=redacted,
            tool_calls=response.tool_calls,
            finish_reason=response.finish_reason,
            usage=response.usage,
        )
