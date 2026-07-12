"""``LlmJudge`` — score a candidate answer with an LLM (LLM-as-judge).

Algorithm:
    1. Receive ``task`` (str), ``candidate`` (str), and ``llm`` (LLMProvider).
    2. Validate types at process time.
    3. Ask the LLM to reply ``SCORE: <0-10>`` followed by feedback.
    4. Parse the numeric score (clamped to 0-10) and feedback into a
       :class:`JudgeVerdict`.

This generalises :class:`~pirn_agents.control.reflection_check.ReflectionCheck`
from a boolean "iterate again?" gate to a continuous score.

References:
    - Zheng et al. (2023) "Judging LLM-as-a-Judge" https://arxiv.org/abs/2306.05685
    - Madaan et al. (2023) "Self-Refine" https://arxiv.org/abs/2303.17651
"""

from __future__ import annotations

import re
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.providers.llm_provider import LLMProvider

from pirn_agents.specializations.evaluator_optimizer.judge_verdict import JudgeVerdict
from pirn_agents.specializations.llm_response_text import extract_response_text


class LlmJudge(Knot):
    """Score a candidate answer, returning a typed :class:`JudgeVerdict`."""

    def __init__(
        self,
        *,
        task: Knot | str,
        candidate: Knot | str,
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(task=task, candidate=candidate, llm=llm, _config=_config, **kwargs)

    async def process(
        self,
        task: str,
        candidate: str,
        llm: LLMProvider,
        **_: Any,
    ) -> JudgeVerdict:
        """Score ``candidate`` against ``task`` and return a :class:`JudgeVerdict`.

        Args:
            task: The original task.
            candidate: The candidate answer to score.
            llm: Provider acting as the judge.

        Returns:
            A :class:`JudgeVerdict` with a 0-10 ``score`` and ``feedback``.

        Raises:
            TypeError: If ``task``/``candidate`` are not strings or ``llm`` is
                not an :class:`LLMProvider`.
        """
        if not isinstance(llm, LLMProvider):
            raise TypeError(f"LlmJudge: llm must be an LLMProvider, got {type(llm).__name__}")
        if not isinstance(task, str):
            raise TypeError(f"LlmJudge: task must be a string, got {type(task).__name__}")
        if not isinstance(candidate, str):
            raise TypeError(f"LlmJudge: candidate must be a string, got {type(candidate).__name__}")
        system = (
            "You are an impartial judge. Rate how well the candidate answers the "
            "task on a 0-10 scale. Reply 'SCORE: <n>' on the first line, then a "
            "short justification."
        )
        user = f"Task:\n{task}\n\nCandidate:\n{candidate}"
        raw = await llm.chat(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ]
        )
        text = extract_response_text(raw)
        return JudgeVerdict(score=self._parse_score(text), feedback=text.strip())

    @staticmethod
    def _parse_score(text: str) -> float:
        match = re.search(r"(\d+(?:\.\d+)?)", text)
        if match is None:
            return 0.0
        value = float(match.group(1))
        if value < 0.0:
            return 0.0
        if value > 10.0:
            return 10.0
        return value
