"""``LatsSearchState`` — the value threaded through the LATS best-first search.

A :class:`~pirn.core.pirn_opaque_value.PirnOpaqueValue`: it carries the live
provider, value model and budget meter each round needs, none of which is
describable to pydantic. Holding them on the loop instead would be graph state
shared by every run of the tapestry (knot-design-rules Rule 4; PIR-874).

:attr:`expanding` is why the state has a field the hand-rolled loop did not need.
``LoopSubTapestry`` hands ``afold`` only the state, so the node ``astep`` is
building a proposal for has to travel in it; selecting that node is therefore
``afold``'s job, not ``astep``'s.

Internal API. See ``lats_step_loop.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.performance.run_budget_meter import RunBudgetMeter
from pirn_agents.specializations.lats.lats_node import LatsNode
from pirn_agents.specializations.lats.trajectory_value_model import TrajectoryValueModel


@dataclass(frozen=True)
class LatsSearchState(PirnOpaqueValue):
    """One expansion's worth of accumulated search state.

    Frozen; the loop returns a new instance rather than mutating.

    Attributes:
        task: The task being searched over.
        llm: Provider the action proposer uses.
        value_model: Scorer for candidate trajectories.
        meter: The budget meter each round spends from.
        max_depth: Trajectory length at which a node is terminal.
        frontier: The best-first queue, heap-ordered over
            ``(-value, sequence, node)``.
        best: The highest-valued node seen so far.
        expanding: The node this round proposes actions for, or ``None`` when the
            search is over.
        nodes_expanded: How many nodes have been popped for expansion.
        budget_exhausted: Whether the budget *stopped* the search. A search whose
            frontier empties first leaves this ``False``, even if the budget is
            fully spent.
        sequence: The next tie-breaking sequence number.
    """

    task: str
    llm: LLMProvider
    value_model: TrajectoryValueModel
    meter: RunBudgetMeter
    max_depth: int
    frontier: tuple[tuple[float, int, LatsNode], ...]
    best: LatsNode
    expanding: LatsNode | None = None
    nodes_expanded: int = 0
    budget_exhausted: bool = False
    sequence: int = 1

    def with_fields(self, **changes: Any) -> LatsSearchState:
        """Return a copy with ``changes`` applied."""
        return replace(self, **changes)

    def _pirn_audit_dict(self) -> dict[str, Any]:
        """Return the lineage-relevant fields, leaving the live collaborators out."""
        return {
            "task": self.task,
            "max_depth": self.max_depth,
            "frontier_size": len(self.frontier),
            "best_value": self.best.value,
            "best_depth": self.best.depth,
            "nodes_expanded": self.nodes_expanded,
            "budget_exhausted": self.budget_exhausted,
        }
