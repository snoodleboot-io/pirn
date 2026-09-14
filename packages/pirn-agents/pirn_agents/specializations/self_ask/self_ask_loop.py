"""``SelfAskLoop`` — the sub-answer loop as a core node.

Replaces the hand-rolled ``for subquestion in subquestions: await
llm.chat(...)`` that ran outside the engine, so each sub-answer is an engine
knot with its own ``Result``, history record, and lineage (ADR
agents-speaks-core WS5b; PIR-856's imperative-loop inventory).

``subquestions`` is a resolved sequence known in full before this loop starts
(decomposition already ran, in ``SelfAskPipeline.process()``, to produce it),
but the loop still uses ``LoopSubTapestry`` rather than a static unroll: the
point is "each sub-answer must be a real, individually-traceable knot", the
same reasoning ``RoundRobinLoop`` documents for ``RoundRobinReview``.

Internal API. See PIR-856.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.specializations.base.agent_loop_pipeline import AgentLoopPipeline
from pirn_agents.specializations.rag.llm_chat_call import LLMChatCall
from pirn_agents.specializations.self_ask.self_ask_state import SelfAskState

if TYPE_CHECKING:
    from pirn.core.run_result import RunResult


class SelfAskLoop(AgentLoopPipeline[SelfAskState]):
    """Answer each sub-question in turn, one ``LLMChatCall`` per round."""

    #: Per-iteration knot id (Rule: no module-level constants).
    _call_id: ClassVar[str] = "call"

    def __init__(
        self,
        *,
        llm: LLMProvider,
        subanswer_system: str,
        **kwargs: Any,
    ) -> None:
        self._llm = llm
        self._subanswer_system = subanswer_system
        super().__init__(**kwargs)

    def step(self, state: SelfAskState) -> tuple[Tapestry, SelfAskState] | None:
        """Build the next sub-question's answer round, or None once all have run.

        Args:
            state: Accumulated state from the previous ``fold``.

        Returns:
            The round's tapestry paired with ``state``, or ``None`` once
            ``state.index`` has walked past the last sub-question.
        """
        if state.index >= len(state.subquestions):
            return None

        round_tapestry = Tapestry()
        with round_tapestry:
            LLMChatCall(
                prompt=state.subquestions[state.index],
                llm=self._llm,
                system=self._subanswer_system,
                _config=KnotConfig(id=self._call_id),
            )
        return round_tapestry, state

    def fold(self, state: SelfAskState, result: RunResult) -> SelfAskState:
        """Append this round's answer and advance the cursor.

        Args:
            state: State as ``step`` returned it.
            result: The round's run result.

        Returns:
            A new state with the answer appended and an advanced index.
        """
        return SelfAskState(
            subquestions=state.subquestions,
            index=state.index + 1,
            subanswers=(*state.subanswers, result.outputs[self._call_id]),
        )

    def step_id(self, state: SelfAskState, idx: int) -> str:
        """Name each round for run history."""
        return f"subanswer_{idx}"
