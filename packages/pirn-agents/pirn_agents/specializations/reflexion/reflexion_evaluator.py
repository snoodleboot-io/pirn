"""``ReflexionEvaluator`` — judge whether an actor attempt satisfies the task.

Algorithm:
    1. Receive ``task`` (str), ``answer`` (str), and ``llm`` (LLMProvider).
    2. Validate types at process time.
    3. Ask the LLM to reply ``PASS`` or ``FAIL: <feedback>``.
    4. Parse the reply into a :class:`ReflexionEvaluation` (success + feedback).

References:
    - Shinn et al. (2023) "Reflexion" https://arxiv.org/abs/2303.11366
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.llm_provider import LLMProvider
from pirn_agents.specializations.llm_response_text import LlmResponseText
from pirn_agents.specializations.reflexion.reflexion_evaluation import ReflexionEvaluation


class ReflexionEvaluator(Knot):
    """Judge an attempt, returning a typed :class:`ReflexionEvaluation`."""

    def __init__(
        self,
        *,
        task: Knot | str,
        answer: Knot | str,
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(task=task, answer=answer, llm=llm, _config=_config, **kwargs)

    async def process(
        self,
        task: str,
        answer: str,
        llm: LLMProvider,
        **_: Any,
    ) -> ReflexionEvaluation:
        """Evaluate ``answer`` against ``task`` and return the verdict.

        Args:
            task: The original task.
            answer: The actor's answer to judge.
            llm: Provider used to make the judgment.

        Returns:
            A :class:`ReflexionEvaluation` with ``success`` and ``feedback``.

        Raises:
            TypeError: If ``task``/``answer`` are not strings or ``llm`` is not
                an :class:`LLMProvider`.
        """
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                f"ReflexionEvaluator: llm must be an LLMProvider, got {type(llm).__name__}"
            )
        if not isinstance(task, str):
            raise TypeError(f"ReflexionEvaluator: task must be a string, got {type(task).__name__}")
        if not isinstance(answer, str):
            raise TypeError(
                f"ReflexionEvaluator: answer must be a string, got {type(answer).__name__}"
            )
        system = (
            "You are a strict evaluator. If the answer fully satisfies the task, "
            "reply with exactly 'PASS'. Otherwise reply 'FAIL: <what to improve>'."
        )
        user = f"Task:\n{task}\n\nAnswer:\n{answer}"
        raw = await llm.chat(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ]
        )
        text = LlmResponseText().extract(raw).strip()
        if text.lower().startswith("pass"):
            return ReflexionEvaluation(success=True, feedback="")
        feedback = (
            text[len("fail") :].lstrip(": ").strip() if text.lower().startswith("fail") else text
        )
        return ReflexionEvaluation(success=False, feedback=feedback)
