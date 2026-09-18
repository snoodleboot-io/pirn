"""A pyedflib too old to redact PHI is refused with a typed error, not a RuntimeError.

Exercises the writer boundary directly with fakes, so no ``pyedflib`` install is
needed: the question is what the format does when the writer in hand exposes
none of the PHI setters, and the answer must be a refusal the caller can catch
by type. Pre-PIR-873 this was a bare ``RuntimeError``.
"""

from __future__ import annotations

import unittest
import warnings

from pirn.connectors.file_formats.bdf_format import BdfFormat
from pirn.connectors.file_formats.edf_format import EdfFormat
from pirn.exceptions.backend_capability_error import BackendCapabilityError


class _WriterWithoutSetters:
    """A pyedflib writer from before the PHI setters existed."""


class _WriterWithOneSetter:
    """A writer that can redact the patient name but nothing else."""

    def __init__(self) -> None:
        self.redacted: list[str] = []

    def setPatientName(self, value: str) -> None:
        self.redacted.append(value)


class TestPhiRedactionCapability(unittest.TestCase):
    def test_edf_refuses_a_writer_that_can_redact_nothing(self) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            with self.assertRaises(BackendCapabilityError) as ctx:
                EdfFormat._apply_phi_redaction(_WriterWithoutSetters())
        self.assertIn("PHI-redaction setters", str(ctx.exception))

    def test_bdf_refuses_a_writer_that_can_redact_nothing(self) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            with self.assertRaises(BackendCapabilityError):
                BdfFormat._apply_phi_redaction(_WriterWithoutSetters())

    def test_edf_accepts_a_writer_that_can_redact_something(self) -> None:
        writer = _WriterWithOneSetter()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            EdfFormat._apply_phi_redaction(writer)
        self.assertEqual(writer.redacted, ["[REDACTED]"])

    def test_bdf_accepts_a_writer_that_can_redact_something(self) -> None:
        writer = _WriterWithOneSetter()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            BdfFormat._apply_phi_redaction(writer)
        self.assertEqual(writer.redacted, ["[REDACTED]"])
