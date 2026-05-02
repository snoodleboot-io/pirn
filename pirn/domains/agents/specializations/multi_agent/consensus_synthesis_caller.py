"""``ConsensusSynthesisCaller`` — LLM-mediated consensus over responses.

Inner stage knot used by :class:`ConsensusAggregator` when the
``llm_synthesis`` strategy is selected. Renders every specialist
response into a single prompt and asks the LLM to produce a
consensus reply. Returns the synthesised :class:`AgentResponse`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider
from pirn.domains.agents.types.agent_response import AgentResponse


class ConsensusSynthesisCaller(Knot):
    """Asks an LLM to synthesise a consensus answer from the inputs."""

    def __init__(
        self,
        *,
        responses: Knot | Mapping[str, AgentResponse],
        llm: LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                "ConsensusSynthesisCaller: llm must be an LLMProvider, "
                f"got {type(llm).__name__}"
            )
        self._llm = llm
        super().__init__(responses=responses, _config=_config, **kwargs)

    async def process(
        self,
        responses: Mapping[str, AgentResponse],
        **_: Any,
    ) -> AgentResponse:
        if not isinstance(responses, Mapping) or not responses:
            raise ValueError(
                "ConsensusSynthesisCaller: responses must be a non-empty "
                "mapping"
            )
        rendered = "\n".join(
            f"[{name}] {response.content}"
            for name, response in responses.items()
        )
        prompt = (
            "You are a consensus synthesiser. Reconcile the following "
            "specialist replies into one coherent answer.\n\n"
            f"Replies:\n{rendered}\n\nConsensus:"
        )
        chat_messages = [{"role": "user", "content": prompt}]
        raw = await self._llm.chat(chat_messages)
        text = self._extract_text(raw)
        return AgentResponse(content=text, finish_reason="stop")

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
