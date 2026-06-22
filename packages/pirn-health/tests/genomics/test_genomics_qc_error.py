"""Tests for :class:`GenomicsQCError`."""

from __future__ import annotations

import unittest

from pirn_health.genomics.genomics_qc_error import GenomicsQCError


class TestGenomicsQCError(unittest.TestCase):
    def test_is_value_error_subclass(self) -> None:
        self.assertTrue(issubclass(GenomicsQCError, ValueError))

    def test_can_be_raised_and_caught(self) -> None:
        with self.assertRaises(GenomicsQCError):
            raise GenomicsQCError("QC below threshold")

    def test_can_be_caught_as_value_error(self) -> None:
        with self.assertRaises(ValueError):
            raise GenomicsQCError("QC below threshold")

    def test_message_preserved(self) -> None:
        try:
            raise GenomicsQCError("read_quality: 15.2 < 20.0")
        except GenomicsQCError as exc:
            self.assertIn("read_quality", str(exc))
