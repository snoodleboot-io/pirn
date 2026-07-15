"""Mirrored tests for the trajectory-quality metrics (S3).

Covers the correct-choice, wrong-choice, and redundant-call scenarios called
out in the story, plus step-efficiency boundaries.
"""

from __future__ import annotations

import unittest

from pirn_agents.evaluation.redundant_call_rate import redundant_call_rate
from pirn_agents.evaluation.step_efficiency import step_efficiency
from pirn_agents.evaluation.tool_choice_accuracy import tool_choice_accuracy
from pirn_agents.evaluation.trajectory import Trajectory
from pirn_agents.evaluation.trajectory_step import TrajectoryStep


def _traj(*names: str) -> Trajectory:
    return Trajectory(steps=[TrajectoryStep(tool_name=n) for n in names])


class ToolChoiceAccuracyTests(unittest.TestCase):
    def test_all_correct_scores_one(self) -> None:
        result = tool_choice_accuracy(actual=_traj("a", "b"), expected=_traj("a", "b"))
        assert result.name == "tool_choice_accuracy"
        assert result.score == 1.0

    def test_wrong_choice_scores_partial(self) -> None:
        result = tool_choice_accuracy(actual=_traj("a", "x"), expected=_traj("a", "b"))
        assert result.score == 0.5

    def test_short_run_penalized_for_missing_positions(self) -> None:
        result = tool_choice_accuracy(actual=_traj("a"), expected=_traj("a", "b"))
        assert result.score == 0.5

    def test_both_empty_scores_one(self) -> None:
        assert tool_choice_accuracy(actual=_traj(), expected=_traj()).score == 1.0

    def test_empty_expected_nonempty_actual_scores_zero(self) -> None:
        assert tool_choice_accuracy(actual=_traj("a"), expected=_traj()).score == 0.0

    def test_match_arguments_distinguishes_same_tool(self) -> None:
        actual = Trajectory(steps=[TrajectoryStep(tool_name="s", arguments={"q": "wrong"})])
        expected = Trajectory(steps=[TrajectoryStep(tool_name="s", arguments={"q": "right"})])
        assert tool_choice_accuracy(actual=actual, expected=expected).score == 1.0
        assert (
            tool_choice_accuracy(actual=actual, expected=expected, match_arguments=True).score
            == 0.0
        )

    def test_non_trajectory_raises(self) -> None:
        with self.assertRaises(TypeError):
            tool_choice_accuracy(actual="x", expected=_traj())  # type: ignore[arg-type]


class StepEfficiencyTests(unittest.TestCase):
    def test_equal_length_scores_one(self) -> None:
        assert step_efficiency(actual=_traj("a", "b"), expected=_traj("a", "b")).score == 1.0

    def test_fewer_steps_scores_one(self) -> None:
        assert step_efficiency(actual=_traj("a"), expected=_traj("a", "b")).score == 1.0

    def test_extra_steps_scores_below_one(self) -> None:
        # 2 expected / 4 actual = 0.5
        assert step_efficiency(
            actual=_traj("a", "b", "c", "d"), expected=_traj("a", "b")
        ).score == (0.5)

    def test_no_steps_taken_when_some_expected_scores_zero(self) -> None:
        assert step_efficiency(actual=_traj(), expected=_traj("a")).score == 0.0

    def test_both_empty_scores_one(self) -> None:
        assert step_efficiency(actual=_traj(), expected=_traj()).score == 1.0


class RedundantCallRateTests(unittest.TestCase):
    def test_no_redundancy_scores_zero(self) -> None:
        result = redundant_call_rate(_traj("a", "b", "c"))
        assert result.name == "redundant_call_rate"
        assert result.score == 0.0

    def test_repeated_identical_call_is_redundant(self) -> None:
        # 4 steps, one repeat of ("a", {}) => 1/4
        result = redundant_call_rate(_traj("a", "b", "a", "c"))
        assert result.score == 0.25
        assert result.detail["redundant"] == 1

    def test_same_tool_different_args_not_redundant(self) -> None:
        traj = Trajectory(
            steps=[
                TrajectoryStep(tool_name="s", arguments={"q": "1"}),
                TrajectoryStep(tool_name="s", arguments={"q": "2"}),
            ]
        )
        assert redundant_call_rate(traj).score == 0.0

    def test_empty_scores_zero(self) -> None:
        assert redundant_call_rate(_traj()).score == 0.0

    def test_non_trajectory_raises(self) -> None:
        with self.assertRaises(TypeError):
            redundant_call_rate([1, 2])  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
