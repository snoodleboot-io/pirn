"""``ConsensusSynthesisCaller`` — LLM-mediated consensus over responses.

Inner stage knot used by :class:`ConsensusAggregator` when the
``llm_synthesis`` strategy is selected. Renders every specialist
response into a single prompt and asks the LLM to produce a
consensus reply. Returns the synthesised :class:`AgentResponse`.

Algorithm:
    1. Render each ``(name, response.content)`` pair into a numbered list.
    2. Build a synthesis prompt instructing the LLM to reconcile replies.
    3. Call ``llm.chat`` with the prompt and extract the text from the reply.
    4. Wrap the extracted text in a new :class:`AgentResponse`.


References:
    pirn-native — no external references.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.providers.llm_provider import LLMProvider

from pirn_agents.types.agent_response import AgentResponse


class ConsensusSynthesisCaller(Knot):
    """Asks an LLM to synthesise a consensus answer from the inputs."""

    def __init__(
        self,
        *,
        responses: Knot | Mapping[str, AgentResponse],
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(responses=responses, llm=llm, _config=_config, **kwargs)

    async def process(
        self,
        responses: Mapping[str, AgentResponse],
        llm: LLMProvider,
        **_: Any,
    ) -> AgentResponse:
        """Feed all specialist responses to the LLM and return its synthesised consensus answer.

        Args:
            responses: A non-empty mapping of specialist names to their AgentResponse outputs.

        Returns:
            A synthesised AgentResponse constructed from the LLM's consensus reply.

        Raises:
            ValueError: If responses is empty or not a Mapping.
        """
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                f"ConsensusSynthesisCaller: llm must be an LLMProvider, got {type(llm).__name__}"
            )
        if not isinstance(responses, Mapping) or not responses:
            raise ValueError("ConsensusSynthesisCaller: responses must be a non-empty mapping")
        rendered = "\n".join(f"[{name}] {response.content}" for name, response in responses.items())
        prompt = (
            "You are a consensus synthesiser. Reconcile the following "
            "specialist replies into one coherent answer.\n\n"
            f"Replies:\n{rendered}\n\nConsensus:"
        )
        chat_messages = [{"role": "user", "content": prompt}]
        raw = await llm.chat(chat_messages)
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
