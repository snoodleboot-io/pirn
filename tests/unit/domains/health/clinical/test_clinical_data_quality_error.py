"""Tests for :class:`ClinicalDataQualityError`."""

from __future__ import annotations

import unittest

from pirn.domains.health.clinical.clinical_data_quality_error import (
    ClinicalDataQualityError,
)


class TestClinicalDataQualityError(unittest.TestCase):
    def test_is_value_error_subclass(self) -> None:
        self.assertTrue(issubclass(ClinicalDataQualityError, ValueError))

    def test_can_be_raised_and_caught(self) -> None:
        with self.assertRaises(ClinicalDataQualityError):
            raise ClinicalDataQualityError("quality below threshold")

    def test_can_be_caught_as_value_error(self) -> None:
        with self.assertRaises(ValueError):
            raise ClinicalDataQualityError("quality below threshold")

    def test_message_preserved(self) -> None:
        try:
            raise ClinicalDataQualityError("dq score: 0.45 < 0.80")
        except ClinicalDataQualityError as exc:
            self.assertIn("dq score", str(exc))
