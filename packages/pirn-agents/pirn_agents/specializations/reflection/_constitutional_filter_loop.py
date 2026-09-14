"""``ConstitutionalFilterLoop`` — the evaluate-and-revise loop as a core node.

Replaces the hand-rolled ``for _i in range(max_revisions): await
llm.chat(...)`` that ran outside the engine, so each evaluation attempt is an
engine knot with its own ``Result``, history record, and lineage (ADR
agents-speaks-core WS5b; PIR-856's imperative-loop inventory).

Internal API. See PIR-856.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.specializations.base.agent_loop_pipeline import AgentLoopPipeline
from pirn_agents.specializations.rag.llm_chat_call import LLMChatCall
from pirn_agents.specializations.reflection._constitutional_state import ConstitutionalState

if TYPE_CHECKING:
    from pirn.core.run_result import RunResult


class ConstitutionalFilterLoop(AgentLoopPipeline[ConstitutionalState]):
    """Evaluate the response against the principles, revising until compliant or exhausted."""

    #: Per-iteration knot id (Rule: no module-level constants).
    _call_id: ClassVar[str] = "call"

    def __init__(
        self,
        *,
        llm: LLMProvider,
        evaluation_system: str,
        max_revisions: int,
        **kwargs: Any,
    ) -> None:
        self._llm = llm
        self._evaluation_system = evaluation_system
        self._max_revisions = max_revisions
        super().__init__(**kwargs)

    def step(self, state: ConstitutionalState) -> tuple[Tapestry, ConstitutionalState] | None:
        """Build the next evaluation attempt, or None once compliant or exhausted.

        Args:
            state: Accumulated state from the previous ``fold``.

        Returns:
            The attempt's tapestry paired with ``state``, or ``None`` once
            ``state.compliant`` or ``state.attempts`` has reached the cap.
        """
        if state.compliant or state.attempts >= self._max_revisions:
            return None

        attempt = Tapestry()
        with attempt:
            LLMChatCall(
                prompt=f"Principles:\n{state.principles_text}\n\nResponse:\n{state.current_content}",
                llm=self._llm,
                system=self._evaluation_system,
                _config=KnotConfig(id=self._call_id),
            )
        return attempt, state

    def fold(self, state: ConstitutionalState, result: RunResult) -> ConstitutionalState:
        """Read the evaluation; compliant stops the loop, else the reply becomes the revision.

        Args:
            state: State as ``step`` returned it.
            result: The attempt's run result.

        Returns:
            A new state, compliant (final) or carrying the revised content.
        """
        evaluation = result.outputs[self._call_id].strip()
        if evaluation.upper() == "COMPLIANT":
            return ConstitutionalState(
                principles_text=state.principles_text,
                current_content=state.current_content,
                attempts=state.attempts + 1,
                compliant=True,
            )
        return ConstitutionalState(
            principles_text=state.principles_text,
            current_content=evaluation,
            attempts=state.attempts + 1,
            compliant=False,
        )

    def step_id(self, state: ConstitutionalState, idx: int) -> str:
        """Name each attempt for run history."""
        return f"revision_{idx}"
