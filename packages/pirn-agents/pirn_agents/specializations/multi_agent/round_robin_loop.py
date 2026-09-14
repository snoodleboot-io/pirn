"""``RoundRobinLoop`` — the sequential reviewer chain as a core node.

Replaces the hand-rolled ``for reviewer in reviewer_list: await
SpecialistHandle.run(...)`` that ran outside the engine, so
every review round is an engine knot with its own ``Result``, history record,
and lineage (ADR agents-speaks-core WS5a; PIR-856's imperative-loop
inventory).

``reviewers`` is a resolved sequence known in full by the time
``RoundRobinReview.process()`` runs, but the loop still uses
``LoopSubTapestry`` rather than a static unroll: the point is not "the count
is unknown" (as for a genuinely open-ended agent loop) but "each round must be
a real, individually-traceable knot" — the same reasoning
``docs/guides/agentic-loops.md`` gives for ``LoopSubTapestry`` over a bare
Python loop. A static unroll (like ``ReActLoop``'s fixed chain) would work
here too; ``LoopSubTapestry`` was chosen to reuse the ``step``/``fold``
machinery this ADR is establishing as the house idiom for "N knots in
sequence, each depending on the last" rather than re-deriving a bespoke
unrolled-chain shape for every such pipeline.

Internal API.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, ClassVar

from pirn.core.knot_config import KnotConfig
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry

from pirn_agents.specializations.base.agent_loop_pipeline import AgentLoopPipeline
from pirn_agents.specializations.multi_agent.reviewer_invocation import (
    ReviewerInvocation,
)
from pirn_agents.specializations.multi_agent.round_robin_state import RoundRobinState
from pirn_agents.specializations.multi_agent.specialist_handle import SpecialistHandle

if TYPE_CHECKING:
    from pirn.core.run_result import RunResult


class RoundRobinLoop(AgentLoopPipeline[RoundRobinState]):
    """Iterate the reviewer sequence, one ``ReviewerInvocation`` per round."""

    #: Per-iteration knot id (Rule: no module-level constants).
    _invoke_id: ClassVar[str] = "invoke"

    def __init__(
        self,
        *,
        reviewers: Sequence[SubTapestry],
        **kwargs: Any,
    ) -> None:
        self._reviewers = tuple(reviewers)
        super().__init__(**kwargs)

    def step(self, state: RoundRobinState) -> tuple[Tapestry, RoundRobinState] | None:
        """Build the next reviewer's round, or return None once all have run.

        Args:
            state: Accumulated state from the previous ``fold``.

        Returns:
            The iteration's tapestry paired with ``state``, or ``None`` once
            ``state.index`` has walked past the last reviewer.
        """
        if state.index >= len(self._reviewers):
            return None

        iteration = Tapestry()
        with iteration:
            ReviewerInvocation(
                reviewer=SpecialistHandle(self._reviewers[state.index]),
                response=state.response,
                _config=KnotConfig(id=self._invoke_id),
            )
        return iteration, state

    def fold(self, state: RoundRobinState, result: RunResult) -> RoundRobinState:
        """Advance the cursor and carry the reviewer's revised draft forward.

        Args:
            state: State as ``step`` returned it.
            result: The round's run result.

        Returns:
            A new state with the revised response and an advanced index.
        """
        return RoundRobinState(
            response=result.outputs[self._invoke_id],
            index=state.index + 1,
        )

    def step_id(self, state: RoundRobinState, idx: int) -> str:
        """Name each round for run history."""
        return f"review_{idx}"
