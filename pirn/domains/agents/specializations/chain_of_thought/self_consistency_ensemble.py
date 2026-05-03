"""``SelfConsistencyEnsemble`` — majority-vote aggregation over N parallel LLM samples."""

from __future__ import annotations

import asyncio
from collections import Counter
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.llm_provider import LLMProvider
from pirn.domains.agents.types.agent_response import AgentResponse


class SelfConsistencyEnsemble(Knot):
    """Run the same prompt N times in parallel and return the majority-vote answer.

    Each sample is sent as an independent LLM call. The final answer is
    determined by a case-insensitive majority vote over the stripped response
    strings. Ties are broken by returning the first-encountered majority
    candidate.
    """

    def __init__(
        self,
        *,
        prompt: Knot | str,
        llm: LLMProvider,
        _config: KnotConfig,
        samples: int = 5,
        **kwargs: Any,
    ) -> None:
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                "SelfConsistencyEnsemble: llm must be an LLMProvider, "
                f"got {type(llm).__name__}"
            )
        if not isinstance(samples, int) or samples <= 0:
            raise ValueError(
                "SelfConsistencyEnsemble: samples must be a positive int, "
                f"got {samples!r}"
            )
        self._llm = llm
        self._samples = samples
        super().__init__(prompt=prompt, _config=_config, **kwargs)

    async def process(self, prompt: str, **_: Any) -> AgentResponse:
        """Run the prompt N times in parallel and return the majority-vote AgentResponse.

        Args:
            prompt: The user question to sample multiple times.

        Returns:
            An AgentResponse whose content is the majority-vote answer across all samples.

        Raises:
            TypeError: If prompt is not a string.
        """
        if not isinstance(prompt, str):
            raise TypeError(
                "SelfConsistencyEnsemble: prompt must be a string, "
                f"got {type(prompt).__name__}"
            )
        messages = [{"role": "user", "content": prompt}]
        tasks = [self._llm.chat(messages=messages) for _ in range(self._samples)]
        raws = await asyncio.gather(*tasks)
        answers = [self._extract_text(raw) for raw in raws]
        winner = self._majority_vote(answers)
        return AgentResponse(content=winner)

    @staticmethod
    def _majority_vote(answers: list[str]) -> str:
        normalised = [a.strip().lower() for a in answers]
        counts: Counter[str] = Counter(normalised)
        top_normal = counts.most_common(1)[0][0]
        for original, norm in zip(answers, normalised):
            if norm == top_normal:
                return original.strip()
        return answers[0].strip()

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
        return str(raw)
