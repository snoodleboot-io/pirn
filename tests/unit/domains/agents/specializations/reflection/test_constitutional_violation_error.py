"""Unit tests for :class:`ConstitutionalViolationError`."""

from __future__ import annotations

import unittest

from pirn.domains.agents.specializations.reflection.constitutional_violation_error import (
    ConstitutionalViolationError,
)


class TestConstitutionalViolationError(unittest.TestCase):
    def test_is_subclass_of_exception(self) -> None:
        assert issubclass(ConstitutionalViolationError, Exception)

    def test_can_be_raised_and_caught(self) -> None:
        with self.assertRaises(ConstitutionalViolationError):
            raise ConstitutionalViolationError("principles violated")

    def test_message_preserved(self) -> None:
        try:
            raise ConstitutionalViolationError("too many violations")
        except ConstitutionalViolationError as exc:
            assert "too many violations" in str(exc)

    def test_can_be_raised_without_message(self) -> None:
        with self.assertRaises(ConstitutionalViolationError):
            raise ConstitutionalViolationError()
