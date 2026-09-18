"""``PromptChainLoop`` — the sequential link chain as a core node.

Replaces the hand-rolled ``for step in step_tuple: await llm.chat(...)`` that
ran outside the engine, so each link is an engine knot with its own
``Result``, history record, and lineage (ADR agents-speaks-core WS5b;
PIR-856's imperative-loop inventory).

``steps`` is a resolved sequence known in full before this loop starts (a
constructor-time value, not decided by an earlier LLM call), but the loop
still uses ``LoopSubTapestry`` rather than a static unroll: each link must be
a real, individually-traceable knot, the same reasoning ``RoundRobinLoop``
documents for ``RoundRobinReview``.

Internal API. See PIR-856.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, ClassVar

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.specializations.base.agent_loop_pipeline import AgentLoopPipeline
from pirn_agents.specializations.prompt_chaining.prompt_chain_state import PromptChainState
from pirn_agents.specializations.rag.llm_chat_call import LLMChatCall

if TYPE_CHECKING:
    from pirn.core.run_result import RunResult


class PromptChainLoop(AgentLoopPipeline[PromptChainState]):
    """Run each link in turn, one ``LLMChatCall`` per link."""

    #: Per-iteration knot id (Rule: no module-level constants).
    _call_id: ClassVar[str] = "call"

    def step(self, state: PromptChainState) -> tuple[Tapestry, PromptChainState] | None:
        """Build the next link's round, or None once every step has run.

        Args:
            state: Accumulated state from the previous ``fold``.

        Returns:
            The round's tapestry paired with ``state``, or ``None`` once
            ``state.index`` has walked past the last step.
        """
        if state.index >= len(state.steps):
            return None

        round_tapestry = Tapestry()
        with round_tapestry:
            LLMChatCall(
                prompt=state.current,
                llm=state.llm,
                system=state.steps[state.index],
                _config=KnotConfig(id=self._call_id),
            )
        return round_tapestry, state

    def fold(self, state: PromptChainState, result: RunResult) -> PromptChainState:
        """Advance the cursor, carrying this link's output as the next link's input.

        Args:
            state: State as ``step`` returned it.
            result: The round's run result.

        Returns:
            A new state with the output appended and an advanced index.
        """
        output = result.outputs[self._call_id]
        return replace(
            state,
            index=state.index + 1,
            current=output,
            outputs=(*state.outputs, output),
        )

    def step_id(self, state: PromptChainState, idx: int) -> str:
        """Name each link for run history."""
        return f"link_{idx}"
