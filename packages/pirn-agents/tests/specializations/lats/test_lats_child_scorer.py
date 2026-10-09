"""Tests for :class:`LatsChildScorer` and :class:`ScoredLatsChild`.

The per-candidate scoring fan-out behind :class:`LatsStepLoop` (PIR-874). The
candidates are only known once the proposer has run, so the fan-out cannot be
declared when the round's tapestry is built — it is an inner run opened
downstream of the proposer, and these tests pin that each candidate becomes its
own knot.
"""

from __future__ import annotations

import unittest
from collections.abc import Sequence

from pirn.backends.in_memory.in_memory_history import InMemoryHistory
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.specializations.lats.lats_child_scorer import LatsChildScorer
from pirn_agents.specializations.lats.lats_node import LatsNode
from pirn_agents.specializations.lats.scored_lats_child import ScoredLatsChild
from pirn_agents.specializations.lats.trajectory_value_model import TrajectoryValueModel


class _LengthValueModel(TrajectoryValueModel):
    """Values a trajectory by the total length of its action strings."""

    async def score(self, task: str, trajectory: Sequence[str]) -> float:
        return float(sum(len(action) for action in trajectory))


class _CountingValueModel(TrajectoryValueModel):
    """Records every trajectory it was asked about."""

    def __init__(self) -> None:
        self.asked: list[tuple[str, ...]] = []

    async def score(self, task: str, trajectory: Sequence[str]) -> float:
        self.asked.append(tuple(trajectory))
        return float(len(trajectory))


class TestScoredLatsChild(unittest.IsolatedAsyncioTestCase):
    async def test_scores_the_trajectory_it_was_given(self) -> None:
        model = _LengthValueModel()
        with Tapestry():
            knot = ScoredLatsChild(
                task="q",
                value_model=model,
                trajectory=("ab", "cde"),
                depth=2,
                _config=KnotConfig(id="child_0"),
            )
        node = await knot.process(task="q", value_model=model, trajectory=("ab", "cde"), depth=2)
        assert node == LatsNode(trajectory=("ab", "cde"), value=5.0, depth=2)

    async def test_scores_the_whole_trajectory_not_just_the_new_action(self) -> None:
        """The value model is asked about the full path from the root."""
        model = _CountingValueModel()
        with Tapestry():
            knot = ScoredLatsChild(
                task="q",
                value_model=model,
                trajectory=("one", "two", "three"),
                depth=3,
                _config=KnotConfig(id="child_0"),
            )
        await knot.process(task="q", value_model=model, trajectory=("one", "two", "three"), depth=3)
        assert model.asked == [("one", "two", "three")]


def _make_scorer(model: TrajectoryValueModel) -> LatsChildScorer:
    with Tapestry():
        return LatsChildScorer(
            task="q",
            value_model=model,
            actions=(),
            trajectory=(),
            depth=0,
            _config=KnotConfig(id="score_children"),
        )


class TestLatsChildScorer(unittest.IsolatedAsyncioTestCase):
    async def test_scores_every_action_as_a_child_of_the_parent(self) -> None:
        model = _LengthValueModel()
        scorer = _make_scorer(model)
        children = await scorer.process(
            task="q",
            value_model=model,
            actions=("left", "right"),
            trajectory=("up",),
            depth=1,
        )
        assert children == (
            LatsNode(trajectory=("up", "left"), value=6.0, depth=2),
            LatsNode(trajectory=("up", "right"), value=7.0, depth=2),
        )

    async def test_keeps_the_proposers_order(self) -> None:
        """Frontier ties are broken by sequence number, so proposal order matters."""
        model = _LengthValueModel()
        scorer = _make_scorer(model)
        children = await scorer.process(
            task="q",
            value_model=model,
            actions=("bb", "aa", "cc"),
            trajectory=(),
            depth=0,
        )
        assert [child.trajectory[-1] for child in children] == ["bb", "aa", "cc"]

    async def test_no_actions_opens_no_inner_run(self) -> None:
        """``Aggregator`` needs a parent, so an empty proposal short-circuits."""
        model = _CountingValueModel()
        scorer = _make_scorer(model)
        children = await scorer.process(
            task="q", value_model=model, actions=(), trajectory=("up",), depth=1
        )
        assert children == ()
        assert model.asked == []

    async def test_each_candidate_gets_its_own_lineage_row(self) -> None:
        """The point of the fan-out: N scoring calls are N knots, not one loop.

        Before PIR-874 the scores were awaited in ``LatsStepLoop.afold``, so a
        round that scored five children recorded one lineage row for the lot.
        """
        history = InMemoryHistory()
        model = _LengthValueModel()
        with Tapestry(history=history) as tapestry:
            LatsChildScorer(
                task="q",
                value_model=model,
                actions=("a", "b", "c"),
                trajectory=(),
                depth=0,
                _config=KnotConfig(id="score_children"),
            )
            result = await tapestry.run(RunRequest())
        assert result.succeeded
        rows = [await history.query_lineage_by_knot_id(f"child_{index}") for index in range(3)]
        assert [len(row) for row in rows] == [1, 1, 1]
        assert all(row[0].outcome == "ok" for row in rows)


class TestProposedOrderIsRestored(unittest.TestCase):
    """The aggregator sorts on the index, whatever order the engine finished in."""

    def test_double_digit_indices_sort_numerically(self) -> None:
        children = {
            f"child_{index}": LatsNode(trajectory=(f"a{index}",), value=0.0, depth=1)
            for index in range(12)
        }
        ordered = LatsChildScorer._in_proposed_order(**children)
        assert [child.trajectory[0] for child in ordered] == [f"a{index}" for index in range(12)]
