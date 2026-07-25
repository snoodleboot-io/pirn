"""Tests for :class:`MetricResult` — validation and audit form."""

from __future__ import annotations

import unittest

from pirn_agents.evaluation.metric_result import MetricResult


class MetricResultTests(unittest.TestCase):
    def test_stores_name_score_and_detail(self) -> None:
        # Arrange / Act
        result = MetricResult(name="exact_match", score=1.0, detail={"k": "v"})

        # Assert
        assert result.name == "exact_match"
        assert result.score == 1.0
        assert result.detail == {"k": "v"}

    def test_detail_defaults_to_empty_mapping(self) -> None:
        result = MetricResult(name="m", score=0.5)
        assert result.detail == {}

    def test_int_score_is_coerced_to_float(self) -> None:
        result = MetricResult(name="m", score=1)
        assert isinstance(result.score, float)
        assert result.score == 1.0

    def test_non_str_name_raises_type_error(self) -> None:
        with self.assertRaises(TypeError):
            MetricResult(name=123, score=1.0)  # type: ignore[arg-type]

    def test_bool_score_is_rejected(self) -> None:
        # Guards against `True` silently coercing to 1.0.
        with self.assertRaises(TypeError):
            MetricResult(name="m", score=True)  # type: ignore[arg-type]

    def test_non_numeric_score_raises_type_error(self) -> None:
        with self.assertRaises(TypeError):
            MetricResult(name="m", score="high")  # type: ignore[arg-type]

    def test_audit_dict_is_primitive(self) -> None:
        result = MetricResult(name="m", score=0.25, detail={"a": 1})
        assert result._pirn_audit_dict() == {"name": "m", "score": 0.25, "detail": {"a": 1}}

    def test_is_frozen(self) -> None:
        result = MetricResult(name="m", score=0.5)
        with self.assertRaises((AttributeError, TypeError)):
            result.score = 0.9  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
