"""``SelfAskPipeline`` — Self-Ask sub-question decomposition.

A :class:`SubTapestry` that:

1. Asks the LLM to decompose the task into follow-up sub-questions (one per
   ``- `` line).
2. Answers each sub-question with the LLM in turn, via
   :class:`~pirn_agents.specializations.self_ask._self_ask_loop.SelfAskLoop`
   (a :class:`~pirn.nodes.loop_sub_tapestry.LoopSubTapestry`) so each
   sub-answer is a real, individually-traceable engine knot rather than a
   step inside a hand-rolled Python ``for`` loop (ADR agents-speaks-core
   WS5b).
3. Composes a final answer from the sub-question/answer pairs via
   :class:`~pirn_agents.specializations.self_ask._self_ask_composer.SelfAskComposer`.

The number of sub-questions is naturally bounded by the decomposition; an empty
decomposition falls back to answering the task directly. Returns a typed
:class:`SelfAskResult`.

References:
    - Press et al. (2022) "Measuring and Narrowing the Compositionality Gap"
      https://arxiv.org/abs/2210.03350
"""

from __future__ import annotations

from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.prompt.prompt_binding import PromptBinding
from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.specializations.llm_response_text import LlmResponseText
from pirn_agents.specializations.self_ask._self_ask_composer import SelfAskComposer
from pirn_agents.specializations.self_ask._self_ask_loop import SelfAskLoop
from pirn_agents.specializations.self_ask._self_ask_state import SelfAskState


class SelfAskPipeline(AgentPipeline):
    """Decompose a task into sub-questions, answer each, then compose."""

    _decompose_system: ClassVar[PromptBinding] = PromptBinding(
        name="specializations.self_ask.self_ask_pipeline.decompose_system",
        default=(
            "Break the question into the follow-up sub-questions needed to "
            "answer it. List each on its own line prefixed with '- '."
        ),
    )

    _subanswer_system: ClassVar[PromptBinding] = PromptBinding(
        name="specializations.self_ask.self_ask_pipeline.subanswer_system",
        default="Answer the sub-question concisely.",
    )

    _compose_system: ClassVar[PromptBinding] = PromptBinding(
        name="specializations.self_ask.self_ask_pipeline.compose_system",
        default="Using the sub-answers, give the final answer to the question.",
    )

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
    ) -> Knot:
        """Run the Self-Ask decomposition and surface a :class:`SelfAskResult`.

        Args:
            task: The question to answer.
            llm: Provider used for decomposition, answering, and composition.
            max_subquestions: Upper bound on sub-questions considered.

        Returns:
            The sink knot whose output is the :class:`SelfAskResult`.

        Raises:
            ValueError: If ``max_subquestions`` is not a positive int.
        """
        if not isinstance(max_subquestions, int) or max_subquestions <= 0:
            raise ValueError(
                "SelfAskPipeline: max_subquestions must be a positive int, got "
                f"{max_subquestions!r}"
            )

        decompose_raw = await llm.chat(
            messages=[
                {
                    "role": "system",
                    "content": type(self)._decompose_system.resolve(),
                },
                {"role": "user", "content": task},
            ]
        )
        subquestions = self._parse_subquestions(LlmResponseText().extract(decompose_raw))[
            :max_subquestions
        ]
        if not subquestions:
            subquestions = (task,)

        initial = Parameter(
            "self_ask_state",
            SelfAskState,
            default=SelfAskState(subquestions=tuple(subquestions), index=0, subanswers=()),
        )
        loop = SelfAskLoop(
            llm=llm,
            subanswer_system=type(self)._subanswer_system.resolve(),
            state=initial,
            _config=KnotConfig(id="self_ask_loop"),
        )
        return SelfAskComposer(
            task=task,
            state=loop,
            llm=llm,
            compose_system=type(self)._compose_system.resolve(),
            _config=KnotConfig(id="self_ask_result"),
        )

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
