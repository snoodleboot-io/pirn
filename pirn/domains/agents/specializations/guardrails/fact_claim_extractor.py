"""``FactClaimExtractor`` — list factual claims emitted by an LLM.

Inner stage knot used by :class:`FactCheckGate`. Renders the supplied
:class:`AgentResponse.content` into a claim-extraction prompt, calls
the configured :class:`LLMProvider`, and parses out one claim per
line. Empty lines and common list markers are stripped.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider
from pirn.domains.agents.types.agent_response import AgentResponse


class FactClaimExtractor(Knot):
    """Asks an LLM to enumerate the factual claims in a response."""

    def __init__(
        self,
        *,
        response: Knot | AgentResponse,
        llm: LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                "FactClaimExtractor: llm must be an LLMProvider, "
                f"got {type(llm).__name__}"
            )
        self._llm = llm
        super().__init__(response=response, _config=_config, **kwargs)

    async def process(
        self,
        response: AgentResponse,
        **_: Any,
    ) -> list[str]:
        """Ask the LLM to enumerate factual claims in the response and return them as a list.

        Args:
            response: The agent response whose content is scanned for factual claims.

        Returns:
            A list of factual claim strings extracted from the response content.

        Raises:
            TypeError: If response is not an AgentResponse instance.
        """
        if not isinstance(response, AgentResponse):
            raise TypeError(
                "FactClaimExtractor: response must be an AgentResponse, "
                f"got {type(response).__name__}"
            )
        prompt = (
            "Extract every factual claim from the answer below. Return one "
            "claim per line; do not editorialise.\n\n"
            f"Answer:\n{response.content}"
        )
        raw = await self._llm.chat(
            [{"role": "user", "content": prompt}]
        )
        text = self._extract_text(raw)
        claims: list[str] = []
        for raw_line in text.splitlines():
            cleaned = raw_line.strip()
            if not cleaned:
                continue
            for marker in ("- ", "* ", "• "):
                if cleaned.startswith(marker):
                    cleaned = cleaned[len(marker):].strip()
                    break
            if cleaned:
                claims.append(cleaned)
        return claims

    @staticmethod
    def _extract_text(raw: Any) -> str:
        if isinstance(raw, str):
            return raw
        if isinstance(raw, dict):
            content = raw.get("content")
            if isinstance(content, str):
                return content
            if isinstance(content, list) and content:
                first = content[0]
                if isinstance(first, dict):
                    text = first.get("text")
                    if isinstance(text, str):
                        return text
                if isinstance(first, str):
                    return first
            text = raw.get("text")
            if isinstance(text, str):
                return text
        return str(raw)
