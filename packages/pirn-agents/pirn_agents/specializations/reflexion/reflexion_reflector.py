"""``ReflexionReflector`` — turn a failed attempt into a reusable verbal lesson.

Algorithm:
    1. Receive ``task``, ``answer``, ``feedback`` (all str) and ``llm``.
    2. Validate types at process time.
    3. Ask the LLM for a short, actionable self-reflection to apply next time.
    4. Return the reflection text (persisted to F4 memory by the pipeline).

References:
    - Shinn et al. (2023) "Reflexion" https://arxiv.org/abs/2303.11366
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.llm_provider import LLMProvider
from pirn_agents.specializations.llm_response_text import LlmResponseText


class ReflexionReflector(Knot):
    """Produce a verbal self-reflection from a failed attempt."""

    def __init__(
        self,
        *,
        task: Knot | str,
        answer: Knot | str,
        feedback: Knot | str,
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            task=task,
            answer=answer,
            feedback=feedback,
            llm=llm,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        task: str,
        answer: str,
        feedback: str,
        llm: LLMProvider,
        **_: Any,
    ) -> str:
        """Produce a concise self-reflection to apply on the next attempt.

        Args:
            task: The original task.
            answer: The failed answer.
            feedback: The evaluator's feedback on ``answer``.
            llm: Provider used to generate the reflection.

        Returns:
            The reflection text.

        Raises:
            TypeError: If any string input has the wrong type or ``llm`` is not
                an :class:`LLMProvider`.
        """
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                f"ReflexionReflector: llm must be an LLMProvider, got {type(llm).__name__}"
            )
        for name, value in (("task", task), ("answer", answer), ("feedback", feedback)):
            if not isinstance(value, str):
                raise TypeError(
                    f"ReflexionReflector: {name} must be a string, got {type(value).__name__}"
                )
        system = (
            "You are reflecting on a failed attempt. Write one short, concrete "
            "lesson (a single sentence) to do better next time."
        )
        user = f"Task:\n{task}\n\nFailed answer:\n{answer}\n\nFeedback:\n{feedback}"
        raw = await llm.chat(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ]
        )
        return LlmResponseText().extract(raw).strip()
