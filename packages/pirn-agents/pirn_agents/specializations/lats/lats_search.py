"""``LatsSearch`` — budgeted best-first tree search over action trajectories.

A :class:`SubTapestry` that performs an MCTS-style (best-first) search: it keeps a
value-ordered frontier of :class:`LatsNode`s, repeatedly expands the most
promising one with :class:`LatsActionProposer`, and scores each child with a
pluggable :class:`TrajectoryValueModel`. Search is **strictly bounded** by an F10
:class:`RunBudget` (a node-count ``max_iterations`` and/or a wall-clock
``deadline_seconds``) enforced through a :class:`RunBudgetMeter`; it never runs
unbounded.

Algorithm:
    1. Validate inputs; require the budget to bound at least one dimension.
    2. Seed the frontier with the root (empty trajectory), scored by the value
       model.
    3. While the frontier is non-empty: spend one node against the meter (a
       breach stops the search cleanly), pop the highest-value node, and — unless
       it is at ``max_depth`` — expand it into scored children pushed back onto
       the frontier. Track the best node seen.
    4. Return a typed :class:`LatsResult` with the best trajectory found.

Math:
    The frontier is a min-heap keyed on :math:`-\\text{value}(n)` (Python's
    :mod:`heapq` is min-first, so negating simulates a max-heap), broken by an
    insertion-order counter so nodes of equal value pop FIFO rather than by an
    unstable trajectory-tuple comparison:

    $$
    \\text{priority}(n) = \\bigl(-\\text{value}(n),\\ \\text{insertion\\_index}(n)\\bigr)
    $$

    ``best`` tracks the single highest-value node seen across the whole
    search, independent of the frontier's current contents:

    $$
    \\text{best} \\leftarrow \\text{child} \\quad \\text{if } \\text{value}(\\text{child}) > \\text{value}(\\text{best})
    $$

    Search halts when the frontier empties, a node reaches ``max_depth``
    without producing a still-frontier-worthy child, or the budget meter
    raises :class:`~pirn_agents.performance.budget_breach_error.BudgetBreachError`
    on ``spend_iteration()`` — whichever comes first.

References:
    - Zhou et al. (2024) "Language Agent Tree Search" https://arxiv.org/abs/2310.04406
"""

from __future__ import annotations

import heapq
import itertools
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.source import Source
from pirn.tapestry import Tapestry

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.performance.budget_breach_error import BudgetBreachError
from pirn_agents.performance.run_budget import RunBudget
from pirn_agents.performance.run_budget_meter import RunBudgetMeter
from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.specializations.lats.lats_action_proposer import LatsActionProposer
from pirn_agents.specializations.lats.lats_node import LatsNode
from pirn_agents.specializations.lats.lats_result import LatsResult
from pirn_agents.specializations.lats.trajectory_value_model import TrajectoryValueModel


class LatsSearch(AgentPipeline):
    """Budget-bounded best-first search over LLM-proposed action trajectories."""

    def __init__(
        self,
        *,
        task: Knot | str,
        llm: Knot | LLMProvider,
        value_model: Knot | TrajectoryValueModel,
        budget: Knot | RunBudget,
        max_depth: Knot | int = 3,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            task=task,
            llm=llm,
            value_model=value_model,
            budget=budget,
            max_depth=max_depth,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        task: str,
        llm: LLMProvider,
        value_model: TrajectoryValueModel,
        budget: RunBudget,
        max_depth: int = 3,
        **_: Any,
    ) -> Knot:
        """Run the budgeted search and surface a :class:`LatsResult`.

        Args:
            task: The task to search over.
            llm: Provider the action proposer uses.
            value_model: Pluggable scorer for trajectories.
            budget: F10 budget bounding node count and/or wall-clock time.
            max_depth: Maximum trajectory length before a node is terminal.

        Returns:
            A terminal :class:`Source` whose output is the :class:`LatsResult`.

        Raises:
            ValueError: If ``max_depth`` < 1 or the budget bounds no dimension.
        """
        if not isinstance(max_depth, int) or max_depth < 1:
            raise ValueError(f"LatsSearch: max_depth must be a positive int, got {max_depth!r}")
        if budget.max_iterations is None and budget.deadline_seconds is None:
            raise ValueError(
                "LatsSearch: budget must bound node count (max_iterations) or time "
                "(deadline_seconds); an unbounded search is not allowed"
            )

        with Tapestry():
            proposer = LatsActionProposer(
                task=task, llm=llm, _config=KnotConfig(id="lats_proposer")
            )

        meter = RunBudgetMeter(budget)
        counter = itertools.count()
        root_value = await value_model.score(task, ())
        root = LatsNode(trajectory=(), value=root_value, depth=0)
        frontier: list[tuple[float, int, LatsNode]] = [(-root_value, next(counter), root)]
        best = root
        nodes_expanded = 0
        budget_exhausted = False

        while frontier:
            try:
                meter.spend_iteration()
            except BudgetBreachError:
                budget_exhausted = True
                break
            _neg_value, _seq, node = heapq.heappop(frontier)
            nodes_expanded += 1
            if node.depth >= max_depth:
                continue
            actions = await proposer.process(task=task, llm=llm, trajectory=node.trajectory)
            for action in actions:
                child_trajectory = (*node.trajectory, action)
                child_value = await value_model.score(task, child_trajectory)
                child = LatsNode(
                    trajectory=child_trajectory,
                    value=child_value,
                    depth=node.depth + 1,
                )
                if child.value > best.value:
                    best = child
                heapq.heappush(frontier, (-child_value, next(counter), child))

        result = LatsResult(
            best_trajectory=best.trajectory,
            best_value=best.value,
            nodes_expanded=nodes_expanded,
            budget_exhausted=budget_exhausted,
        )
        _result = result

        class _LatsResultSource(Source):
            async def process(self, **_: Any) -> LatsResult:
                return _result

        return _LatsResultSource(_config=KnotConfig(id="lats_result"))
