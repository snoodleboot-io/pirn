"""Mirrored tests for the :class:`LLMJudge` harness and its bias controls (S4)."""

from __future__ import annotations

import unittest

from pirn_agents.evaluation.llm_judge import LLMJudge
from pirn_agents.evaluation.rubric_criterion import RubricCriterion
from tests.evaluation.evaluation_doubles import ScriptedJudgeProvider


class RubricModeTests(unittest.IsolatedAsyncioTestCase):
    async def test_weighted_overall_across_criteria(self) -> None:
        # correctness=1.0 (weight 3), style=0.0 (weight 1) => 3/4 = 0.75
        judge = LLMJudge(judge=ScriptedJudgeProvider(["1.0", "0.0"]))
        score = await judge.score_rubric(
            prompt="q",
            response="r",
            criteria=[
                RubricCriterion(name="correctness", weight=3.0),
                RubricCriterion(name="style", weight=1.0),
            ],
        )
        assert score.overall == 0.75
        assert score.per_criterion == {"correctness": 1.0, "style": 0.0}

    async def test_self_consistency_averages_samples(self) -> None:
        # two samples for the single criterion: 1.0 and 0.0 => mean 0.5
        judge = LLMJudge(judge=ScriptedJudgeProvider(["1.0", "0.0"]), self_consistency=2)
        score = await judge.score_rubric(
            prompt="q", response="r", criteria=[RubricCriterion(name="c")]
        )
        assert score.overall == 0.5
        assert score.detail["self_consistency"] == 2

    async def test_empty_criteria_raises(self) -> None:
        judge = LLMJudge(judge=ScriptedJudgeProvider(["1.0"]))
        with self.assertRaises(ValueError):
            await judge.score_rubric(prompt="q", response="r", criteria=[])

    async def test_non_provider_judge_raises(self) -> None:
        with self.assertRaises(TypeError):
            LLMJudge(judge=object())  # type: ignore[arg-type]

    async def test_zero_self_consistency_raises(self) -> None:
        with self.assertRaises(ValueError):
            LLMJudge(judge=ScriptedJudgeProvider(["1"]), self_consistency=0)


class PairwiseModeTests(unittest.IsolatedAsyncioTestCase):
    async def test_a_wins_single_order(self) -> None:
        judge = LLMJudge(judge=ScriptedJudgeProvider(["A"]))
        outcome = await judge.compare_pairwise(prompt="q", response_a="ra", response_b="rb")
        assert outcome.winner == "a"
        assert outcome.score_a == 1.0
        assert outcome.consistent is True

    async def test_position_swap_consistent_winner(self) -> None:
        # order1 (A=ra,B=rb): judge says "A" -> ra wins;
        # order2 (A=rb,B=ra): judge says "B" -> ra wins again -> consistent
        judge = LLMJudge(judge=ScriptedJudgeProvider(["A", "B"]), position_swap=True)
        outcome = await judge.compare_pairwise(prompt="q", response_a="ra", response_b="rb")
        assert outcome.winner == "a"
        assert outcome.consistent is True

    async def test_position_swap_detects_position_bias(self) -> None:
        # Judge always says "A" regardless of which real response is shown first:
        # order1 -> ra wins; order2 -> rb wins -> orders disagree -> forced tie.
        judge = LLMJudge(judge=ScriptedJudgeProvider(["A", "A"]), position_swap=True)
        outcome = await judge.compare_pairwise(prompt="q", response_a="ra", response_b="rb")
        assert outcome.winner == "tie"
        assert outcome.consistent is False

    async def test_self_consistency_majority_vote(self) -> None:
        # 3 votes: A, A, B -> a wins 2/3
        judge = LLMJudge(judge=ScriptedJudgeProvider(["A", "A", "B"]), self_consistency=3)
        outcome = await judge.compare_pairwise(prompt="q", response_a="ra", response_b="rb")
        assert outcome.winner == "a"
        assert round(outcome.score_a, 4) == round(2 / 3, 4)


if __name__ == "__main__":
    unittest.main()
