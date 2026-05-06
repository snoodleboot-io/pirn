"""Tests for QualityCheck."""

from __future__ import annotations

import unittest

from pirn.domains.data.quality_check import QualityCheck


class TestQualityCheckConstruction(unittest.TestCase):
    def test_passing_check(self) -> None:
        qc = QualityCheck(name="null_rate", passed=True, threshold="<5%", actual="2%")
        self.assertEqual(qc.name, "null_rate")
        self.assertTrue(qc.passed)
        self.assertEqual(qc.threshold, "<5%")
        self.assertEqual(qc.actual, "2%")
        self.assertIsNone(qc.column)

    def test_failing_check(self) -> None:
        qc = QualityCheck(name="row_count", passed=False, threshold=">100", actual="50")
        self.assertFalse(qc.passed)

    def test_with_column(self) -> None:
        qc = QualityCheck(
            name="null_rate",
            passed=True,
            threshold="<10%",
            actual="0%",
            column="user_id",
        )
        self.assertEqual(qc.column, "user_id")

    def test_frozen(self) -> None:
        qc = QualityCheck(name="x", passed=True, threshold="t", actual="a")
        with self.assertRaises((AttributeError, TypeError)):
            qc.passed = False  # type: ignore[misc]

    def test_equality(self) -> None:
        a = QualityCheck(name="x", passed=True, threshold="t", actual="a")
        b = QualityCheck(name="x", passed=True, threshold="t", actual="a")
        self.assertEqual(a, b)
