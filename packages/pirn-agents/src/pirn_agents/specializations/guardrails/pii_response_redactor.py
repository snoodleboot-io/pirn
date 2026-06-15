"""``PIIResponseRedactor`` — regex-driven PII redaction over a response.

Inner stage knot used by :class:`PiiRedactorCheck`. Walks each compiled
PII pattern against the supplied :class:`AgentResponse.content` and
replaces matches with the literal ``"<redacted>"``. Returns a new
:class:`AgentResponse` with the redacted content; ``tool_calls``,
``finish_reason`` and ``usage`` are forwarded unchanged.

Algorithm:
    1. Validate that ``response`` is an :class:`AgentResponse`; raise
       :class:`TypeError` otherwise.
    2. Compile each raw string in ``patterns`` into a regex via
       :func:`compile_safe_pattern`.
    3. Apply each compiled pattern sequentially to ``response.content``
       using :meth:`re.Pattern.sub`, replacing matches with
       ``"<redacted>"``.
    4. If the resulting string equals the original content, return the
       original :class:`AgentResponse` unchanged.
    5. Otherwise construct and return a new :class:`AgentResponse` with
       the redacted content and all other fields forwarded unchanged.


References:
    - pirn-native: :class:`pirn_agents.types.agent_response.AgentResponse`
    - pirn-native: :func:`pirn_agents._regex_utils.compile_safe_pattern`
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents._regex_utils import compile_safe_pattern
from pirn_agents.types.agent_response import AgentResponse


class PIIResponseRedactor(Knot):
    """Redacts PII matches in :class:`AgentResponse.content`."""

    def __init__(
        self,
        *,
        response: Knot | AgentResponse,
        patterns: Knot | Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(response=response, patterns=patterns, _config=_config, **kwargs)

    async def process(
        self,
        response: AgentResponse,
        patterns: Sequence[str] = (),
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
        compiled = tuple(
            compile_safe_pattern(raw, index=i, owner="PIIResponseRedactor", field="patterns")
            for i, raw in enumerate(patterns)
        )
        content = response.content

        def _apply_pii(content_str: str = content) -> str:
            for p in compiled:
                content_str = p.sub("<redacted>", content_str)
            return content_str

        redacted = await asyncio.to_thread(_apply_pii)
        if redacted == response.content:
            return response
        return AgentResponse(
            content=redacted,
            tool_calls=response.tool_calls,
            finish_reason=response.finish_reason,
            usage=response.usage,
        )
