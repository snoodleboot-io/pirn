"""``LatsStepLoop`` — expand one LATS frontier node per iteration.

A best-first tree search: which node is expanded next depends on every score so
far, and how many expansions happen depends on the budget. The shape is unknown
until the run, which is exactly what ``LoopSubTapestry`` is for
(knot-design-rules Rule 11) — unlike a chain or a fan-out, whose shape is fixed
when the graph is built.

It replaces a hand-rolled ``while frontier:`` that awaited ``_run_inner`` once per
expansion, so every expansion's lineage sat in its own unrelated run (PIR-874).

Each round's tapestry proposes the actions *and* scores them: the candidates are
only known once the proposer has run, so the per-candidate fan-out lives in
:class:`~pirn_agents.specializations.lats.lats_child_scorer.LatsChildScorer`
downstream of it.  ``afold`` is then pure bookkeeping — it was awaiting the value
model once per child, which gave the whole round one lineage row for N scoring
calls (Rule 11; PIR-874).

Where the accounting lives
--------------------------
``astep`` returning ``None`` ends the loop *without* a fold, so anything it
counted would be thrown away. Every change to the search's bookkeeping therefore
happens in :meth:`advance`, which ``LatsSearch.process`` calls once to seed the
state and :meth:`afold` calls once per round. ``astep`` only reads.

:meth:`advance` keeps the hand-rolled order exactly: check the frontier, spend the
round's budget, pop, count, and skip a node already at ``max_depth`` by going
round again — so a terminal pop costs a budget spend, as it did before, and a
breach stops the search and records that the *budget* stopped it.

Internal API.
"""

from __future__ import annotations

import heapq
from typing import Any, ClassVar

from pirn.core.knot_config import KnotConfig
from pirn.core.run_result import RunResult
from pirn.tapestry import Tapestry

from pirn_agents.performance.budget_breach_error import BudgetBreachError
from pirn_agents.specializations.base.agent_loop_pipeline import AgentLoopPipeline
from pirn_agents.specializations.lats.lats_action_proposer import LatsActionProposer
from pirn_agents.specializations.lats.lats_child_scorer import LatsChildScorer
from pirn_agents.specializations.lats.lats_search_state import LatsSearchState


class LatsStepLoop(AgentLoopPipeline[LatsSearchState]):
    """Expand the frontier's best node each round until the budget or frontier ends."""

    #: Per-iteration knot ids (Rule: no module-level constants).
    _propose_id: ClassVar[str] = "propose"
    _score_id: ClassVar[str] = "score_children"

    @staticmethod
    def advance(state: LatsSearchState) -> LatsSearchState:
        """Select the next node to expand, spending the round's budget.

        Args:
            state: The state whose frontier the next node is drawn from.

        Returns:
            A state whose ``expanding`` is the node to propose actions for, or
            ``None`` when the frontier is empty or the budget stopped the search.
        """
        frontier = list(state.frontier)
        expanded = state.nodes_expanded
        while True:
            if not frontier:
                return state.with_fields(
                    frontier=tuple(frontier), expanding=None, nodes_expanded=expanded
                )
            try:
                state.meter.spend_iteration()
            except BudgetBreachError:
                return state.with_fields(
                    frontier=tuple(frontier),
                    expanding=None,
                    nodes_expanded=expanded,
                    budget_exhausted=True,
                )
            _neg_value, _sequence, node = heapq.heappop(frontier)
            expanded += 1
            if node.depth < state.max_depth:
                return state.with_fields(
                    frontier=tuple(frontier), expanding=node, nodes_expanded=expanded
                )

    async def astep(self, state: LatsSearchState) -> tuple[Tapestry, LatsSearchState] | None:
        """Build the selected node's proposal, or ``None`` when the search is over.

        Reads only: :meth:`advance` has already done the selection and the
        accounting.

        Args:
            state: Accumulated state from the previous ``afold``.

        Returns:
            The round's tapestry paired with the state ``afold`` will receive, or
            ``None`` once there is nothing left to expand.
        """
        node = state.expanding
        if node is None:
            return None
        with Tapestry() as iteration:
            proposer = LatsActionProposer(
                task=state.task,
                llm=state.llm,
                trajectory=node.trajectory,
                _config=KnotConfig(id=type(self)._propose_id),
            )
            LatsChildScorer(
                task=state.task,
                value_model=state.value_model,
                actions=proposer,
                trajectory=node.trajectory,
                depth=node.depth,
                _config=KnotConfig(id=type(self)._score_id),
            )
        return iteration, state

    async def afold(self, state: LatsSearchState, result: RunResult) -> LatsSearchState:
        """Queue the expanded node's children, then select the next node.

        Pure bookkeeping: the round's tapestry has already proposed the actions
        and scored each of them (see ``LatsChildScorer``), so nothing here
        awaits a collaborator.

        Args:
            state: State as ``astep`` returned it.
            result: The round's run result, whose scorer output is the children.

        Returns:
            A state with the children queued, ``best`` updated, and the next node
            selected (or the search ended).
        """
        if state.expanding is None:
            return state
        children: Any = result.outputs[type(self)._score_id]
        frontier = list(state.frontier)
        best = state.best
        sequence = state.sequence
        for child in children:
            if child.value > best.value:
                best = child
            heapq.heappush(frontier, (-child.value, sequence, child))
            sequence += 1
        queued = state.with_fields(frontier=tuple(frontier), best=best, sequence=sequence)
        return LatsStepLoop.advance(queued)

    def step_id(self, state: LatsSearchState, idx: int) -> str:
        """Name each expansion for run history."""
        return f"expansion_{idx}"
