"""Mirrored tests for the RAG metrics (S2) using stub judge/embedding doubles.

Scoring boundaries are asserted for each metric: fully faithful, contradictory,
irrelevant context, and (for answer relevance) on- vs off-topic answers.
"""

from __future__ import annotations

import unittest

from pirn_agents.evaluation.answer_relevance_metric import AnswerRelevanceMetric
from pirn_agents.evaluation.context_precision_metric import ContextPrecisionMetric
from pirn_agents.evaluation.context_recall_metric import ContextRecallMetric
from pirn_agents.evaluation.faithfulness_metric import FaithfulnessMetric
from pirn_agents.evaluation.rag_sample import RagSample
from tests.evaluation.evaluation_doubles import (
    ScriptedJudgeProvider,
    StubEmbeddingProvider,
    bag_of_words_embedder,
)


class FaithfulnessMetricTests(unittest.IsolatedAsyncioTestCase):
    async def test_fully_faithful_scores_one(self) -> None:
        judge = ScriptedJudgeProvider(["yes", "yes"])
        sample = RagSample(
            query="q",
            contexts=["Paris is the capital of France."],
            answer="Paris is the capital. France is in Europe.",
        )
        result = await FaithfulnessMetric(judge=judge).evaluate(sample)
        assert result.name == "faithfulness"
        assert result.score == 1.0
        assert result.detail["claims"] == 2

    async def test_contradictory_answer_scores_zero(self) -> None:
        judge = ScriptedJudgeProvider(["no", "no"])
        sample = RagSample(query="q", contexts=["ctx"], answer="Wrong one. Wrong two.")
        result = await FaithfulnessMetric(judge=judge).evaluate(sample)
        assert result.score == 0.0

    async def test_partial_support_scores_half(self) -> None:
        judge = ScriptedJudgeProvider(["yes", "no"])
        sample = RagSample(query="q", contexts=["ctx"], answer="Right. Wrong.")
        result = await FaithfulnessMetric(judge=judge).evaluate(sample)
        assert result.score == 0.5

    async def test_empty_answer_is_vacuously_faithful(self) -> None:
        result = await FaithfulnessMetric(judge=ScriptedJudgeProvider(["no"])).evaluate(
            RagSample(query="q", contexts=["ctx"], answer="")
        )
        assert result.score == 1.0

    async def test_non_provider_judge_raises(self) -> None:
        with self.assertRaises(TypeError):
            FaithfulnessMetric(judge=object())  # type: ignore[arg-type]


class ContextPrecisionMetricTests(unittest.IsolatedAsyncioTestCase):
    async def test_relevant_first_scores_one(self) -> None:
        judge = ScriptedJudgeProvider(["yes", "no"])
        sample = RagSample(query="q", contexts=["relevant", "irrelevant"])
        result = await ContextPrecisionMetric(judge=judge).evaluate(sample)
        assert result.name == "context_precision"
        assert result.score == 1.0

    async def test_relevant_last_scores_below_one(self) -> None:
        # relevant chunk at rank 2 => precision@2 = 1/2 => score 0.5
        judge = ScriptedJudgeProvider(["no", "yes"])
        sample = RagSample(query="q", contexts=["irrelevant", "relevant"])
        result = await ContextPrecisionMetric(judge=judge).evaluate(sample)
        assert result.score == 0.5

    async def test_all_irrelevant_scores_zero(self) -> None:
        judge = ScriptedJudgeProvider(["no", "no"])
        sample = RagSample(query="q", contexts=["a", "b"])
        result = await ContextPrecisionMetric(judge=judge).evaluate(sample)
        assert result.score == 0.0

    async def test_empty_contexts_scores_zero(self) -> None:
        result = await ContextPrecisionMetric(judge=ScriptedJudgeProvider(["yes"])).evaluate(
            RagSample(query="q", contexts=[])
        )
        assert result.score == 0.0


class ContextRecallMetricTests(unittest.IsolatedAsyncioTestCase):
    async def test_all_attributable_scores_one(self) -> None:
        judge = ScriptedJudgeProvider(["yes", "yes"])
        sample = RagSample(
            query="q",
            contexts=["ctx"],
            answer="a",
            ground_truth="Fact one. Fact two.",
        )
        result = await ContextRecallMetric(judge=judge).evaluate(sample)
        assert result.name == "context_recall"
        assert result.score == 1.0

    async def test_half_attributable_scores_half(self) -> None:
        judge = ScriptedJudgeProvider(["yes", "no"])
        sample = RagSample(query="q", contexts=["ctx"], ground_truth="One. Two.")
        result = await ContextRecallMetric(judge=judge).evaluate(sample)
        assert result.score == 0.5

    async def test_missing_ground_truth_raises(self) -> None:
        with self.assertRaises(ValueError):
            await ContextRecallMetric(judge=ScriptedJudgeProvider(["yes"])).evaluate(
                RagSample(query="q", contexts=["ctx"])
            )


class AnswerRelevanceMetricTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.embedder = StubEmbeddingProvider(
            bag_of_words_embedder(["capital", "france", "paris", "weather", "rain"])
        )

    async def test_on_topic_answer_scores_high(self) -> None:
        sample = RagSample(
            query="capital of france",
            answer="paris is the capital of france",
        )
        result = await AnswerRelevanceMetric(embedder=self.embedder).evaluate(sample)
        assert result.name == "answer_relevance"
        assert result.score > 0.5

    async def test_off_topic_answer_scores_zero(self) -> None:
        sample = RagSample(query="capital france", answer="weather rain")
        result = await AnswerRelevanceMetric(embedder=self.embedder).evaluate(sample)
        assert result.score == 0.0

    async def test_non_embedding_provider_raises(self) -> None:
        with self.assertRaises(TypeError):
            AnswerRelevanceMetric(embedder=object())  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
