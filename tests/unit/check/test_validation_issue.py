"""Tests for ValidationIssue."""

from __future__ import annotations

import unittest

from pirn.check.validation_issue import ValidationIssue


class TestValidationIssueConstruction(unittest.TestCase):
    def test_error_with_knot_id(self) -> None:
        issue = ValidationIssue(severity="error", knot_id="my_knot", message="duplicate id")
        self.assertEqual(issue.severity, "error")
        self.assertEqual(issue.knot_id, "my_knot")
        self.assertEqual(issue.message, "duplicate id")

    def test_warning_without_knot_id(self) -> None:
        issue = ValidationIssue(severity="warning", knot_id=None, message="no knots")
        self.assertIsNone(issue.knot_id)

    def test_str_with_knot_id(self) -> None:
        issue = ValidationIssue(severity="error", knot_id="k1", message="oops")
        result = str(issue)
        self.assertIn("ERROR", result)
        self.assertIn("[k1]", result)
        self.assertIn("oops", result)

    def test_str_without_knot_id(self) -> None:
        issue = ValidationIssue(severity="warning", knot_id=None, message="global warning")
        result = str(issue)
        self.assertIn("WARNING", result)
        self.assertNotIn("[", result)
        self.assertIn("global warning", result)

    def test_severity_uppercased_in_str(self) -> None:
        issue = ValidationIssue(severity="error", knot_id=None, message="x")
        self.assertTrue(str(issue).startswith("ERROR"))

    def test_equality_via_dataclass(self) -> None:
        a = ValidationIssue("error", "k1", "msg")
        b = ValidationIssue("error", "k1", "msg")
        self.assertEqual(a, b)

    def test_inequality(self) -> None:
        a = ValidationIssue("error", "k1", "msg")
        b = ValidationIssue("warning", "k1", "msg")
        self.assertNotEqual(a, b)
