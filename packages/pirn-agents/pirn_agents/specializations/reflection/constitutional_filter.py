"""``ConstitutionalFilter`` — evaluate and revise a response against a set of principles.

A :class:`SubTapestry` that drives the evaluate-and-revise loop with
:class:`~pirn_agents.specializations.reflection._constitutional_filter_loop._ConstitutionalFilterLoop`
(a :class:`~pirn.nodes.loop_sub_tapestry.LoopSubTapestry`): each revision
attempt is a real, individually-traceable ``LLMChatCall`` knot instead of a
step inside a hand-rolled Python ``for`` loop (ADR agents-speaks-core WS5b;
PIR-856's imperative-loop inventory).

Algorithm:
    1. Format the principles as a bulleted list.
    2. For each revision attempt (up to ``max_revisions``):
       a. Ask the LLM to evaluate the current response against the principles.
       b. If the LLM responds with exactly ``COMPLIANT``, return the current response.
       c. Otherwise treat the LLM's output as the revised response and continue.
    3. If violations persist after all attempts, raise :class:`ConstitutionalViolationError`.


References:
    - Bai et al., "Constitutional AI: Harmlessness from AI Feedback", 2022.
      https://arxiv.org/abs/2212.08073
"""

from __future__ import annotations

from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.prompt.prompt_binding import PromptBinding
from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.specializations.reflection._constitutional_filter_loop import (
    _ConstitutionalFilterLoop,
)
from pirn_agents.specializations.reflection._constitutional_result_extractor import (
    _ConstitutionalResultExtractor,
)
from pirn_agents.specializations.reflection._constitutional_state import _ConstitutionalState
from pirn_agents.types.messaging.agent_response import AgentResponse


class ConstitutionalFilter(AgentPipeline):
    """Evaluate a response against constitutional principles and revise until compliant.

    For each revision attempt the LLM is asked to identify any violations of
    the supplied principles and to produce a revised response that addresses
    them. If the LLM reports no violations the current response is returned
    immediately. If violations remain after ``max_revisions`` attempts,
    :class:`ConstitutionalViolationError` is raised.
    """

    _evaluation_system: ClassVar[PromptBinding] = PromptBinding(
        name="specializations.reflection.constitutional_filter.evaluation_system",
        default=(
            "You are a constitutional AI reviewer. Evaluate the response against "
            "the principles listed below. If the response violates any principle, "
            "describe the violation and provide a revised response that is compliant. "
            "If the response is fully compliant, reply with exactly: COMPLIANT"
        ),
    )

    def __init__(
        self,
        *,
        response: Knot,
        principles: Knot | tuple[str, ...] | list[str],
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        max_revisions: Knot | int = 3,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            response=response,
            principles=principles,
            llm=llm,
            max_revisions=max_revisions,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        response: AgentResponse,
        principles: tuple[str, ...] | list[str],
        llm: LLMProvider,
        max_revisions: int = 3,
        **_: Any,
    ) -> Knot:
        """Wire the revision loop and return its compliance-extracting sink knot.

        Args:
            response: The AgentResponse to evaluate against the constitutional principles.
            principles: A sequence of principle strings the response must satisfy.
            llm: The LLMProvider to use for evaluation and revision.
            max_revisions: Maximum number of revision attempts before raising.

        Returns:
            The sink knot whose output is a compliant :class:`AgentResponse`.

        Raises:
            ValueError: If max_revisions is not a positive int.
        """
        if not isinstance(max_revisions, int) or max_revisions <= 0:
            raise ValueError(
                f"ConstitutionalFilter: max_revisions must be a positive int, got {max_revisions!r}"
            )
        principles_text = "\n".join(f"- {p}" for p in principles)

        initial = Parameter(
            "constitutional_state",
            _ConstitutionalState,
            default=_ConstitutionalState(
                principles_text=principles_text,
                current_content=response.content,
                attempts=0,
                compliant=False,
            ),
        )
        loop = _ConstitutionalFilterLoop(
            llm=llm,
            evaluation_system=type(self)._evaluation_system.resolve(),
            max_revisions=max_revisions,
            state=initial,
            _config=KnotConfig(id="constitutional_loop"),
        )
        return _ConstitutionalResultExtractor(state=loop, _config=KnotConfig(id="result"))
