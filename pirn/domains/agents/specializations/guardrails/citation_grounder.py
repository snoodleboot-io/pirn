"""``CitationGrounder`` — rewrite AgentResponse with inline source citations.

A :class:`Knot` that asks an LLM to rewrite the content of an
:class:`AgentResponse` so that each claim includes an inline citation
referencing the supplied source document passages. Returns a new
:class:`AgentResponse` with the grounded content.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider
from pirn.domains.agents.types.agent_response import AgentResponse


class CitationGrounder(Knot):
    """Rewrite an AgentResponse to include inline citations to source passages."""

    def __init__(
        self,
        *,
        response: Knot | AgentResponse,
        sources: Knot | Sequence[str],
        llm: LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                "CitationGrounder: llm must be an LLMProvider, "
                f"got {type(llm).__name__}"
            )
        self._llm = llm
        super().__init__(
            response=response, sources=sources, _config=_config, **kwargs
        )

    async def process(
        self,
        response: AgentResponse,
        sources: Sequence[str],
        **_: Any,
    ) -> AgentResponse:
        """Rewrite the response content with inline citations and return it.

        Args:
            response: The agent response to ground with citations.
            sources: A sequence of source document strings to cite from.

        Returns:
            A new AgentResponse with the content rewritten to include inline citations.

        Raises:
            TypeError: If response is not an AgentResponse instance.
        """
        if not isinstance(response, AgentResponse):
            raise TypeError(
                "CitationGrounder: response must be an AgentResponse, "
                f"got {type(response).__name__}"
            )
        sources_text = "\n\n".join(
            f"[{i + 1}]: {src}" for i, src in enumerate(sources)
        )
        prompt = (
            "Rewrite the following response to include inline citations "
            "referencing the numbered source passages below. "
            "Use the format [N] after each supported claim.\n\n"
            f"Sources:\n{sources_text}\n\n"
            f"Response:\n{response.content}"
        )
        raw = await self._llm.chat([{"role": "user", "content": prompt}])
        new_content = self._extract_text(raw).strip()
        return AgentResponse(
            content=new_content,
            tool_calls=response.tool_calls,
            finish_reason=response.finish_reason,
            usage=response.usage,
        )

    @staticmethod
    def _extract_text(raw: Any) -> str:
        if isinstance(raw, str):
            return raw
        if isinstance(raw, dict):
            content = raw.get("content")
            if isinstance(content, str):
                return content
        return str(raw)
