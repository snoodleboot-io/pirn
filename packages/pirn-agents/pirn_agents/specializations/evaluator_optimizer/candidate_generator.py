"""``CandidateGenerator`` — produce a candidate answer, optionally from feedback.

Algorithm:
    1. Receive ``task`` (str), ``llm`` (LLMProvider), and prior ``feedback`` (str).
    2. Validate types at process time.
    3. When feedback is present, instruct the model to improve on it.
    4. Call the LLM once and return the candidate text.

References:
    - Madaan et al. (2023) "Self-Refine" https://arxiv.org/abs/2303.17651
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.llm_provider import LLMProvider
from pirn_agents.specializations.llm_response_text import LlmResponseText


class CandidateGenerator(Knot):
    """Generate a candidate answer for the task, refining on prior feedback."""

    def __init__(
        self,
        *,
        task: Knot | str,
        llm: Knot | LLMProvider,
        feedback: Knot | str = "",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(task=task, llm=llm, feedback=feedback, _config=_config, **kwargs)

    async def process(
        self,
        task: str,
        llm: LLMProvider,
        feedback: str = "",
        **_: Any,
    ) -> str:
        """Generate a candidate answer, improving on ``feedback`` when present.

        Args:
            task: The task to answer.
            llm: Provider used to generate the candidate.
            feedback: Prior judge feedback to improve upon; empty on round one.

        Returns:
            The candidate answer text.

        Raises:
            TypeError: If ``task``/``feedback`` are not strings or ``llm`` is not
                an :class:`LLMProvider`.
        """
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                f"CandidateGenerator: llm must be an LLMProvider, got {type(llm).__name__}"
            )
        if not isinstance(task, str):
            raise TypeError(f"CandidateGenerator: task must be a string, got {type(task).__name__}")
        if not isinstance(feedback, str):
            raise TypeError(
                f"CandidateGenerator: feedback must be a string, got {type(feedback).__name__}"
            )
        system = "You are a careful writer. Produce the best answer you can to the task."
        user = task if not feedback else f"{task}\n\nImprove on this feedback:\n{feedback}"
        raw = await llm.chat(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ]
        )
        return LlmResponseText().extract(raw)
