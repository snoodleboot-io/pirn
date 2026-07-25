"""Tests for :class:`TaskSuccess`."""

from __future__ import annotations

import unittest

from pirn_agents.evaluation.task_success import TaskSuccess


class TaskSuccessTests(unittest.TestCase):
    def test_true_flag_scores_one(self) -> None:
        result = TaskSuccess().score(True)
        assert result.name == "task_success"
        assert result.score == 1.0

    def test_false_flag_scores_zero(self) -> None:
        assert TaskSuccess().score(False).score == 0.0

    def test_structured_end_state_equality(self) -> None:
        result = TaskSuccess().score({"status": "done"}, {"status": "done"})
        assert result.score == 1.0

    def test_structured_end_state_mismatch(self) -> None:
        result = TaskSuccess().score({"status": "error"}, {"status": "done"})
        assert result.score == 0.0

    def test_empty_output_against_default_expected_fails(self) -> None:
        # An empty string is not equal to the default expected `True`.
        assert TaskSuccess().score("").score == 0.0

    def test_detail_records_both_outcomes(self) -> None:
        result = TaskSuccess().score("a", "b")
        assert result.detail == {"actual": "'a'", "expected": "'b'"}


if __name__ == "__main__":
    unittest.main()
