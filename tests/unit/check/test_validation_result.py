"""Tests for ValidationResult."""

from __future__ import annotations

import unittest

from pirn.check.validation_issue import ValidationIssue
from pirn.check.validation_result import ValidationResult


class TestValidationResultProperties(unittest.TestCase):
    def test_empty_is_ok(self) -> None:
        result = ValidationResult()
        self.assertTrue(result.ok)
        self.assertEqual(result.errors, [])
        self.assertEqual(result.warnings, [])

    def test_error_makes_not_ok(self) -> None:
        result = ValidationResult(issues=[
            ValidationIssue("error", None, "boom")
        ])
        self.assertFalse(result.ok)

    def test_warning_does_not_affect_ok(self) -> None:
        result = ValidationResult(issues=[
            ValidationIssue("warning", None, "just a note")
        ])
        self.assertTrue(result.ok)

    def test_errors_filters_correctly(self) -> None:
        issues = [
            ValidationIssue("error", None, "e1"),
            ValidationIssue("warning", None, "w1"),
            ValidationIssue("error", "k1", "e2"),
        ]
        result = ValidationResult(issues=issues)
        self.assertEqual(len(result.errors), 2)
        self.assertEqual(len(result.warnings), 1)

    def test_warnings_filters_correctly(self) -> None:
        result = ValidationResult(issues=[
            ValidationIssue("warning", None, "w"),
            ValidationIssue("warning", None, "w2"),
        ])
        self.assertEqual(len(result.warnings), 2)
        self.assertEqual(result.errors, [])

    def test_issues_default_empty(self) -> None:
        result = ValidationResult()
        self.assertEqual(result.issues, [])

    def test_mixed_issues_appended(self) -> None:
        result = ValidationResult()
        result.issues.append(ValidationIssue("error", "x", "msg"))
        self.assertFalse(result.ok)
