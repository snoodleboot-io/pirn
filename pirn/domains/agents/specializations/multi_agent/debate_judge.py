"""``DebateJudge`` — LLM judge that picks the strongest debate response.

Inner stage knot used by :class:`DebateFramework`. Renders the topic
plus every debater's final response into a judging prompt and asks
``judge_llm`` to pick a winner by index. Returns the chosen
:class:`AgentResponse`. Falls back to the first response if the
judge's reply does not name a valid index.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider
from pirn.domains.agents.types.agent_response import AgentResponse


class DebateJudge(Knot):
    """Picks the winning :class:`AgentResponse` from a debate round."""

    def __init__(
        self,
        *,
        topic: Knot | str,
        final_round: Knot | Sequence[AgentResponse],
        judge_llm: LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(judge_llm, LLMProvider):
            raise TypeError(
                "DebateJudge: judge_llm must be an LLMProvider, "
                f"got {type(judge_llm).__name__}"
            )
        self._judge_llm = judge_llm
        super().__init__(
            topic=topic,
            final_round=final_round,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        topic: str,
        final_round: Sequence[AgentResponse],
        **_: Any,
    ) -> AgentResponse:
        responses = tuple(final_round)
        if not responses:
            raise ValueError(
                "DebateJudge: final_round must contain at least one response"
            )
        rendered = "\n".join(
            f"[{index}] {response.content}"
            for index, response in enumerate(responses)
        )
        prompt = (
            "You are a debate judge. Pick the strongest argument by index.\n"
            f"Topic: {topic}\n\n"
            f"Arguments:\n{rendered}\n\n"
            "Reply with the winning index only."
        )
        raw = await self._judge_llm.chat(
            [{"role": "user", "content": prompt}]
        )
        text = self._extract_text(raw).strip()
        for token in text.replace(",", " ").split():
            cleaned = token.strip("[]().: ")
            if cleaned.isdigit():
                index = int(cleaned)
                if 0 <= index < len(responses):
                    return responses[index]
        return responses[0]

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
