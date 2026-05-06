"""Tests for QualityReport."""

from __future__ import annotations

import unittest
from datetime import datetime

from pirn.domains.data.quality_check import QualityCheck
from pirn.domains.data.quality_report import QualityReport


def _check(name: str, passed: bool) -> QualityCheck:
    return QualityCheck(name=name, passed=passed, threshold="t", actual="a")


class TestQualityReportConstruction(unittest.TestCase):
    def test_empty_passed_report(self) -> None:
        r = QualityReport(passed=True)
        self.assertTrue(r.passed)
        self.assertEqual(r.checks, ())
        self.assertEqual(r.row_count, 0)
        self.assertIsInstance(r.sampled_at, datetime)

    def test_all_checks_pass(self) -> None:
        r = QualityReport(
            passed=True,
            checks=(_check("null_rate", True), _check("row_count", True)),
        )
        self.assertTrue(r.passed)
        self.assertEqual(r.failed_checks, ())

    def test_failed_check_makes_passed_false(self) -> None:
        r = QualityReport(
            passed=False,
            checks=(_check("null_rate", False),),
        )
        self.assertFalse(r.passed)
        self.assertEqual(len(r.failed_checks), 1)

    def test_inconsistent_passed_true_with_failure_raises(self) -> None:
        with self.assertRaises(ValueError):
            QualityReport(
                passed=True,
                checks=(_check("null_rate", False),),
            )

    def test_failed_checks_property(self) -> None:
        r = QualityReport(
            passed=False,
            checks=(
                _check("a", True),
                _check("b", False),
                _check("c", True),
                _check("d", False),
            ),
        )
        failed = r.failed_checks
        self.assertEqual(len(failed), 2)
        self.assertTrue(all(not c.passed for c in failed))

    def test_frozen(self) -> None:
        r = QualityReport(passed=True)
        with self.assertRaises((AttributeError, TypeError)):
            r.passed = False  # type: ignore[misc]
