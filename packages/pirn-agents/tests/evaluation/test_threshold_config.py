"""Tests for :class:`MetricThreshold` / :class:`ThresholdConfig` (S6)."""

from __future__ import annotations

import unittest

from pirn_agents.evaluation.metric_threshold import MetricThreshold
from pirn_agents.evaluation.threshold_config import ThresholdConfig


class MetricThresholdTests(unittest.TestCase):
    def test_passes_at_or_above_min(self) -> None:
        threshold = MetricThreshold(metric="faithfulness", min_score=0.8)
        assert threshold.passes(0.8) is True
        assert threshold.passes(0.9) is True
        assert threshold.passes(0.79) is False

    def test_non_str_metric_raises(self) -> None:
        with self.assertRaises(TypeError):
            MetricThreshold(metric=1, min_score=0.5)  # type: ignore[arg-type]

    def test_non_numeric_min_raises(self) -> None:
        with self.assertRaises(TypeError):
            MetricThreshold(metric="m", min_score="high")  # type: ignore[arg-type]


class ThresholdConfigTests(unittest.TestCase):
    def test_min_for_returns_configured_or_none(self) -> None:
        config = ThresholdConfig(thresholds=[MetricThreshold(metric="m", min_score=0.7)])
        assert config.min_for("m") == 0.7
        assert config.min_for("absent") is None

    def test_duplicate_metric_raises(self) -> None:
        with self.assertRaises(ValueError):
            ThresholdConfig(
                thresholds=[
                    MetricThreshold(metric="m", min_score=0.5),
                    MetricThreshold(metric="m", min_score=0.6),
                ]
            )

    def test_non_threshold_element_raises(self) -> None:
        with self.assertRaises(TypeError):
            ThresholdConfig(thresholds=["nope"])  # type: ignore[list-item]

    def test_json_roundtrip(self) -> None:
        config = ThresholdConfig(
            thresholds=[
                MetricThreshold(metric="faithfulness", min_score=0.8),
                MetricThreshold(metric="answer_relevance", min_score=0.7),
            ]
        )
        assert ThresholdConfig.from_json(config.to_json()) == config


if __name__ == "__main__":
    unittest.main()
