"""``SelfAskPipeline`` — Self-Ask sub-question decomposition.

A :class:`SubTapestry` that:

1. Asks the LLM to decompose the task into follow-up sub-questions (one per
   ``- `` line).
2. Answers each sub-question with the LLM in turn.
3. Composes a final answer from the sub-question/answer pairs.

The number of sub-questions is naturally bounded by the decomposition; an empty
decomposition falls back to answering the task directly. Returns a typed
:class:`SelfAskResult`.

References:
    - Press et al. (2022) "Measuring and Narrowing the Compositionality Gap"
      https://arxiv.org/abs/2210.03350
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.providers.llm_provider import LLMProvider
from pirn.nodes.source import Source
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_agents.specializations.llm_response_text import LlmResponseText
from pirn_agents.specializations.self_ask.self_ask_result import SelfAskResult


class SelfAskPipeline(SubTapestry):
    """Decompose a task into sub-questions, answer each, then compose."""

    def __init__(
        self,
        *,
        task: Knot | str,
        llm: Knot | LLMProvider,
        max_subquestions: Knot | int = 5,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            task=task,
            llm=llm,
            max_subquestions=max_subquestions,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        task: str,
        llm: LLMProvider,
        max_subquestions: int = 5,
        **_: Any,
    ) -> Any:
        """Run the Self-Ask decomposition and surface a :class:`SelfAskResult`.

        Args:
            task: The question to answer.
            llm: Provider used for decomposition, answering, and composition.
            max_subquestions: Upper bound on sub-questions considered.

        Returns:
            A terminal :class:`Source` whose output is the :class:`SelfAskResult`.

        Raises:
            TypeError: If ``task`` is not a string or ``llm`` is not an
                :class:`LLMProvider`.
            ValueError: If ``max_subquestions`` is not a positive int.
        """
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                f"SelfAskPipeline: llm must be an LLMProvider, got {type(llm).__name__}"
            )
        if not isinstance(task, str):
            raise TypeError(f"SelfAskPipeline: task must be a string, got {type(task).__name__}")
        if not isinstance(max_subquestions, int) or max_subquestions <= 0:
            raise ValueError(
                "SelfAskPipeline: max_subquestions must be a positive int, got "
                f"{max_subquestions!r}"
            )

        decompose_raw = await llm.chat(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Break the question into the follow-up sub-questions needed to "
                        "answer it. List each on its own line prefixed with '- '."
                    ),
                },
                {"role": "user", "content": task},
            ]
        )
        subquestions = self._parse_subquestions(LlmResponseText().extract(decompose_raw))[
            :max_subquestions
        ]
        if not subquestions:
            subquestions = (task,)

        subanswers: list[str] = []
        for subquestion in subquestions:
            answer_raw = await llm.chat(
                messages=[
                    {"role": "system", "content": "Answer the sub-question concisely."},
                    {"role": "user", "content": subquestion},
                ]
            )
            subanswers.append(LlmResponseText().extract(answer_raw))

        pairs = "\n".join(f"Q: {q}\nA: {a}" for q, a in zip(subquestions, subanswers, strict=True))
        final_raw = await llm.chat(
            messages=[
                {
                    "role": "system",
                    "content": "Using the sub-answers, give the final answer to the question.",
                },
                {"role": "user", "content": f"Question:\n{task}\n\n{pairs}"},
            ]
        )
        result = SelfAskResult(
            final_answer=LlmResponseText().extract(final_raw),
            subquestions=tuple(subquestions),
            subanswers=tuple(subanswers),
        )
        _result = result

        class _SelfAskResultSource(Source):
            async def process(self, **_: Any) -> SelfAskResult:
                return _result

        return _SelfAskResultSource(_config=KnotConfig(id="self_ask_result"))

    @staticmethod
    def _parse_subquestions(text: str) -> tuple[str, ...]:
        questions: list[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("- "):
                question = stripped[2:].strip()
                if question:
                    questions.append(question)
        return tuple(questions)
