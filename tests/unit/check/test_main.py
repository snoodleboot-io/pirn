"""Tests for check.main."""

from __future__ import annotations

import io
import sys
import unittest
from unittest.mock import MagicMock, patch

from pirn.check.main import main
from pirn.check.validation_issue import ValidationIssue
from pirn.check.validation_result import ValidationResult


class TestMainReturnCodes(unittest.TestCase):
    def _build_tapestry(self, result: ValidationResult):
        """Return a factory callable that produces a mock tapestry."""
        tap = MagicMock()
        tap._store.all.return_value = []
        return tap, result

    def test_ok_result_returns_0(self) -> None:
        tap = MagicMock()
        tap._store.all.return_value = []
        ok_result = ValidationResult()

        with patch("pirn.check.main._load_factory", return_value=lambda: tap):
            with patch("pirn.check.main.validate_tapestry", return_value=ok_result):
                code = main(["mymod:build"])
        self.assertEqual(code, 0)

    def test_error_result_returns_1(self) -> None:
        tap = MagicMock()
        error_result = ValidationResult(issues=[
            ValidationIssue("error", None, "cycle detected")
        ])

        with patch("pirn.check.main._load_factory", return_value=lambda: tap):
            with patch("pirn.check.main.validate_tapestry", return_value=error_result):
                code = main(["mymod:build"])
        self.assertEqual(code, 1)

    def test_strict_mode_warning_returns_1(self) -> None:
        tap = MagicMock()
        warn_result = ValidationResult(issues=[
            ValidationIssue("warning", None, "too many terminals")
        ])

        with patch("pirn.check.main._load_factory", return_value=lambda: tap):
            with patch("pirn.check.main.validate_tapestry", return_value=warn_result):
                code = main(["mymod:build", "--strict"])
        self.assertEqual(code, 1)

    def test_warning_without_strict_returns_0(self) -> None:
        tap = MagicMock()
        warn_result = ValidationResult(issues=[
            ValidationIssue("warning", None, "too many terminals")
        ])

        with patch("pirn.check.main._load_factory", return_value=lambda: tap):
            with patch("pirn.check.main.validate_tapestry", return_value=warn_result):
                code = main(["mymod:build"])
        self.assertEqual(code, 0)

    def test_factory_raises_returns_2(self) -> None:
        def bad_factory():
            raise RuntimeError("bad")

        with patch("pirn.check.main._load_factory", return_value=bad_factory):
            code = main(["mymod:build"])
        self.assertEqual(code, 2)
