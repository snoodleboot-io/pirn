"""Tests for :class:`StructuredOutputCapability`."""

from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError

from pirn_agents.specializations.structured_output.structured_output_capability import (
    StructuredOutputCapability,
)


class TestStructuredOutputCapability(unittest.TestCase):
    def test_defaults_advertise_no_native_support(self) -> None:
        capability = StructuredOutputCapability()

        assert capability.native_schema is False
        assert capability.forced_tool_choice is False
        assert capability.constrained_decoding is False

    def test_flags_are_settable_independently(self) -> None:
        capability = StructuredOutputCapability(
            native_schema=True, forced_tool_choice=False, constrained_decoding=True
        )

        assert capability.native_schema is True
        assert capability.forced_tool_choice is False
        assert capability.constrained_decoding is True

    def test_is_frozen(self) -> None:
        capability = StructuredOutputCapability()

        with self.assertRaises(FrozenInstanceError):
            capability.native_schema = True  # type: ignore[misc]

    def test_value_equality(self) -> None:
        assert StructuredOutputCapability(native_schema=True) == StructuredOutputCapability(
            native_schema=True
        )


if __name__ == "__main__":
    unittest.main()
