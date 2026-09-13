"""``_ScoreCandidate`` — ask the LLM to rate one candidate reasoning path."""

from __future__ import annotations

from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.prompt.prompt_binding import PromptBinding
from pirn_agents.specializations.llm_response_text import LlmResponseText


class _ScoreCandidate(Knot):
    """Ask the LLM to rate one candidate reasoning path."""

    _scoring_system: ClassVar[PromptBinding] = PromptBinding(
        name="specializations.chain_of_thought.tree_of_thought.scoring_system",
        default=(
            "You are a reasoning evaluator. Rate the quality of the following "
            "reasoning step on a scale from 1 to 10. Reply with a single integer only."
        ),
    )

    def __init__(
        self,
        *,
        candidate: Knot | tuple[str, float],
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(candidate=candidate, llm=llm, _config=_config, **kwargs)

    async def process(
        self, candidate: tuple[str, float], llm: LLMProvider, **_: Any
    ) -> tuple[str, float]:
        """Score ``candidate``'s path.

        Args:
            candidate: The ``(path, placeholder_score)`` pair to score.
            llm: The provider used to rate the path.

        Returns:
            A ``(path, score)`` pair; ``score`` defaults to 0.0 when the LLM's
            reply does not parse as a float.

        Math:
            Score :math:`s \\in \\{0\\} \\cup [1, 10]` as judged by the LLM;
            0 when its reply does not parse as a number.
        """
        path, _placeholder = candidate
        messages = [
            {"role": "system", "content": _ScoreCandidate._scoring_system.resolve()},
            {"role": "user", "content": path},
        ]
        raw = await llm.chat(messages=messages)
        text = LlmResponseText().extract(raw).strip()
        try:
            return path, float(text)
        except ValueError:
            return path, 0.0
