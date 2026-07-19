"""``ReflexionActor`` — produce an answer, conditioned on prior reflections.

Algorithm:
    1. Receive ``task`` (str), ``llm`` (LLMProvider), and ``reflections``
       (tuple of prior verbal self-reflection strings read back from memory).
    2. Validate types at process time.
    3. Prepend the accumulated reflections to the prompt so the actor learns
       from earlier failed attempts.
    4. Call the LLM once and return the answer text.

References:
    - Shinn et al. (2023) "Reflexion" https://arxiv.org/abs/2303.11366
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.llm_provider import LLMProvider
from pirn_agents.specializations.llm_response_text import LlmResponseText


class ReflexionActor(Knot):
    """Generate an answer for the task, informed by prior reflections."""

    def __init__(
        self,
        *,
        task: Knot | str,
        llm: Knot | LLMProvider,
        reflections: Knot | Sequence[str] = (),
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            task=task,
            llm=llm,
            reflections=reflections,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        task: str,
        llm: LLMProvider,
        reflections: Sequence[str] = (),
        **_: Any,
    ) -> str:
        """Produce an answer for the task, conditioned on prior reflections.

        Args:
            task: The task to answer.
            llm: Provider used to generate the answer.
            reflections: Prior self-reflection strings from earlier attempts.

        Returns:
            The answer text.

        Raises:
            TypeError: If ``task`` is not a string or ``llm`` is not an
                :class:`LLMProvider`.
        """
        if not isinstance(llm, LLMProvider):
            raise TypeError(f"ReflexionActor: llm must be an LLMProvider, got {type(llm).__name__}")
        if not isinstance(task, str):
            raise TypeError(f"ReflexionActor: task must be a string, got {type(task).__name__}")
        reflection_tuple = tuple(reflections)
        system = "You are a diligent problem solver. Answer the task as well as you can."
        if reflection_tuple:
            lessons = "\n".join(f"- {text}" for text in reflection_tuple)
            system = f"{system}\nApply these lessons from earlier attempts:\n{lessons}"
        raw = await llm.chat(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": task},
            ]
        )
        return LlmResponseText().extract(raw)
