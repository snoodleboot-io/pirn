"""Mirrored tests for the trajectory-quality metrics (S3).

Covers the correct-choice, wrong-choice, and redundant-call scenarios called
out in the story, plus step-efficiency boundaries.
"""

from __future__ import annotations

import unittest

from pirn_agents.evaluation.redundant_call_rate import RedundantCallRate
from pirn_agents.evaluation.step_efficiency import StepEfficiency
from pirn_agents.evaluation.tool_choice_accuracy import ToolChoiceAccuracy
from pirn_agents.evaluation.trajectory import Trajectory
from pirn_agents.evaluation.trajectory_call_key import TrajectoryCallKey
from pirn_agents.evaluation.trajectory_step import TrajectoryStep


def _traj(*names: str) -> Trajectory:
    return Trajectory(steps=[TrajectoryStep(tool_name=n) for n in names])


class ToolChoiceAccuracyTests(unittest.TestCase):
    def test_all_correct_scores_one(self) -> None:
        result = ToolChoiceAccuracy().score(_traj("a", "b"), _traj("a", "b"))
        assert result.name == "tool_choice_accuracy"
        assert result.score == 1.0

    def test_wrong_choice_scores_partial(self) -> None:
        result = ToolChoiceAccuracy().score(_traj("a", "x"), _traj("a", "b"))
        assert result.score == 0.5

    def test_short_run_penalized_for_missing_positions(self) -> None:
        result = ToolChoiceAccuracy().score(_traj("a"), _traj("a", "b"))
        assert result.score == 0.5

    def test_both_empty_scores_one(self) -> None:
        assert ToolChoiceAccuracy().score(_traj(), _traj()).score == 1.0

    def test_empty_expected_nonempty_actual_scores_zero(self) -> None:
        assert ToolChoiceAccuracy().score(_traj("a"), _traj()).score == 0.0

    def test_match_arguments_distinguishes_same_tool(self) -> None:
        actual = Trajectory(steps=[TrajectoryStep(tool_name="s", arguments={"q": "wrong"})])
        expected = Trajectory(steps=[TrajectoryStep(tool_name="s", arguments={"q": "right"})])
        assert ToolChoiceAccuracy().score(actual, expected).score == 1.0
        assert ToolChoiceAccuracy(match_arguments=True).score(actual, expected).score == 0.0

    def test_non_trajectory_raises(self) -> None:
        with self.assertRaises(TypeError):
            ToolChoiceAccuracy().score("x", _traj())  # type: ignore[arg-type]


class StepEfficiencyTests(unittest.TestCase):
    def test_equal_length_scores_one(self) -> None:
        assert StepEfficiency().score(_traj("a", "b"), _traj("a", "b")).score == 1.0

    def test_fewer_steps_scores_one(self) -> None:
        assert StepEfficiency().score(_traj("a"), _traj("a", "b")).score == 1.0

    def test_extra_steps_scores_below_one(self) -> None:
        # 2 expected / 4 actual = 0.5
        assert StepEfficiency().score(_traj("a", "b", "c", "d"), _traj("a", "b")).score == (0.5)

    def test_no_steps_taken_when_some_expected_scores_zero(self) -> None:
        assert StepEfficiency().score(_traj(), _traj("a")).score == 0.0

    def test_both_empty_scores_one(self) -> None:
        assert StepEfficiency().score(_traj(), _traj()).score == 1.0


class RedundantCallRateTests(unittest.TestCase):
    def test_no_redundancy_scores_zero(self) -> None:
        result = RedundantCallRate().score(_traj("a", "b", "c"))
        assert result.name == "redundant_call_rate"
        assert result.score == 0.0

    def test_repeated_identical_call_is_redundant(self) -> None:
        # 4 steps, one repeat of ("a", {}) => 1/4
        result = RedundantCallRate().score(_traj("a", "b", "a", "c"))
        assert result.score == 0.25
        assert result.detail["redundant"] == 1

    def test_same_tool_different_args_not_redundant(self) -> None:
        traj = Trajectory(
            steps=[
                TrajectoryStep(tool_name="s", arguments={"q": "1"}),
                TrajectoryStep(tool_name="s", arguments={"q": "2"}),
            ]
        )
        assert RedundantCallRate().score(traj).score == 0.0

    def test_empty_scores_zero(self) -> None:
        assert RedundantCallRate().score(_traj()).score == 0.0

    def test_non_trajectory_raises(self) -> None:
        with self.assertRaises(TypeError):
            RedundantCallRate().score([1, 2])  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()


class _AddressOnly:
    """A step argument whose only rendering is its memory address."""


class _ContentRendered:
    """A step argument that renders its content."""

    def __init__(self, amount: int) -> None:
        self.amount = amount

    def __str__(self) -> str:
        return f"_ContentRendered({self.amount})"


class TrajectoryCallKeyContentKeyingTests(unittest.TestCase):
    """PIR-826 — the key promises stability, so it must not key on an address."""

    # ---- what actually changed: the address-keyed case is now refused -------
    #
    # Note the shape of this fix. An argument that renders content — anything
    # with its own __str__, plus datetime/UUID/Decimal/Path/Enum — was ALREADY
    # keyed correctly by the previous `default=str`, and still is, byte for
    # byte. So there is no "used to score wrong, now scores right" case to
    # assert: the repair is that the *unfixable* case stops producing a number
    # at all. Only an argument whose sole rendering is its memory address was
    # ever broken, and for that no stable key exists to compute.

    def test_address_keyed_argument_is_refused(self) -> None:
        with self.assertRaises(TypeError):
            TrajectoryCallKey().args_key({"handle": _AddressOnly()})

    def test_redundant_call_rate_declines_rather_than_under_reporting(self) -> None:
        # Before: each _AddressOnly rendered to a different address, so two
        # identical calls looked unique and the metric returned 0.0 — a wrong
        # number, silently. Now it refuses to produce one.
        traj = Trajectory(
            steps=[
                TrajectoryStep(tool_name="s", arguments={"handle": _AddressOnly()}),
                TrajectoryStep(tool_name="s", arguments={"handle": _AddressOnly()}),
            ]
        )
        with self.assertRaises(TypeError):
            RedundantCallRate().score(traj)

    def test_tool_choice_accuracy_declines_rather_than_scoring_a_match_wrong(self) -> None:
        # Before: returned 0.0 for a call that was in fact correct.
        actual = Trajectory(
            steps=[TrajectoryStep(tool_name="s", arguments={"handle": _AddressOnly()})]
        )
        expected = Trajectory(
            steps=[TrajectoryStep(tool_name="s", arguments={"handle": _AddressOnly()})]
        )
        with self.assertRaises(TypeError):
            ToolChoiceAccuracy(match_arguments=True).score(actual, expected)

    # ---- preservation: everything that worked keeps working, unchanged ------

    def test_identical_content_in_distinct_instances_is_one_key(self) -> None:
        key = TrajectoryCallKey()
        assert key.args_key({"amount": _ContentRendered(5)}) == key.args_key(
            {"amount": _ContentRendered(5)}
        )

    def test_key_is_order_independent(self) -> None:
        key = TrajectoryCallKey()
        assert key.args_key({"a": 1, "b": 2}) == key.args_key({"b": 2, "a": 1})

    def test_content_rendering_arguments_still_score(self) -> None:
        traj = Trajectory(
            steps=[
                TrajectoryStep(tool_name="s", arguments={"amount": _ContentRendered(5)}),
                TrajectoryStep(tool_name="s", arguments={"amount": _ContentRendered(5)}),
            ]
        )
        assert RedundantCallRate().score(traj).score == 0.5
        one = Trajectory(
            steps=[TrajectoryStep(tool_name="s", arguments={"amount": _ContentRendered(5)})]
        )
        assert ToolChoiceAccuracy(match_arguments=True).score(one, one).score == 1.0
