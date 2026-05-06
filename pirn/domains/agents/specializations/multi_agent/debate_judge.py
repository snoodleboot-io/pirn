"""``DebateJudge`` — LLM judge that picks the strongest debate response.

Inner stage knot used by :class:`DebateFramework`. Renders the topic
plus every debater's final response into a judging prompt and asks
``judge_llm`` to pick a winner by index. Returns the chosen
:class:`AgentResponse`. Falls back to the first response if the
judge's reply does not name a valid index.

Algorithm:
    1. Render each debater's final response as ``[index] content``.
    2. Build a judging prompt instructing the LLM to reply with an index.
    3. Call ``judge_llm.chat`` and extract the text reply.
    4. Parse the first digit token from the reply; select that response.
    5. Fall back to ``final_round[0]`` if no valid index is found.


References:
    pirn-native — no external references.
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
        judge_llm: Knot | LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            topic=topic,
            final_round=final_round,
            judge_llm=judge_llm,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        topic: str,
        final_round: Sequence[AgentResponse],
        judge_llm: LLMProvider,
        **_: Any,
    ) -> AgentResponse:
        """Ask the judge LLM to pick the strongest argument by index and return that AgentResponse.

        Args:
            topic: The debate topic string used to frame the judging prompt.
            final_round: The sequence of AgentResponse instances from the last debate round.

        Returns:
            The AgentResponse selected by the judge; falls back to the first response on parse failure.

        Raises:
            ValueError: If final_round is empty.
        """
        if not isinstance(judge_llm, LLMProvider):
            raise TypeError(
                f"DebateJudge: judge_llm must be an LLMProvider, got {type(judge_llm).__name__}"
            )
        responses = tuple(final_round)
        if not responses:
            raise ValueError("DebateJudge: final_round must contain at least one response")
        rendered = "\n".join(
            f"[{index}] {response.content}" for index, response in enumerate(responses)
        )
        prompt = (
            "You are a debate judge. Pick the strongest argument by index.\n"
            f"Topic: {topic}\n\n"
            f"Arguments:\n{rendered}\n\n"
            "Reply with the winning index only."
        )
        raw = await judge_llm.chat([{"role": "user", "content": prompt}])
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
