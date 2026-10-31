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

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.performance.run_budget import RunBudget
from pirn_agents.performance.run_budget_meter import RunBudgetMeter
from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.specializations.lats.lats_node import LatsNode
from pirn_agents.specializations.lats.lats_result_extractor import LatsResultExtractor
from pirn_agents.specializations.lats.lats_search_state import LatsSearchState
from pirn_agents.specializations.lats.lats_step_loop import LatsStepLoop
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
            The sink knot whose output is the :class:`LatsResult`.

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

        root_value = await value_model.score(task, ())
        root = LatsNode(trajectory=(), value=root_value, depth=0)
        seeded = LatsSearchState(
            task=task,
            llm=llm,
            value_model=value_model,
            meter=RunBudgetMeter(budget),
            max_depth=max_depth,
            frontier=((-root_value, 0, root),),
            best=root,
        )
        # Core owns the iteration: one run with one traceable expansion per round,
        # rather than a round trip and an unrelated run for each (Rule 11;
        # PIR-874). ``advance`` seeds the first selection so every change to the
        # search's bookkeeping happens in one place.
        loop = LatsStepLoop(
            state=LatsStepLoop.advance(seeded),
            _config=KnotConfig(id="lats_search"),
        )
        return LatsResultExtractor(state=loop, _config=KnotConfig(id="lats_result"))
