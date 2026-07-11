"""Tests for :class:`ConstrainedDecodingMapper` (F20-S3)."""

from __future__ import annotations

import sys
import types
import unittest
from unittest import mock

from pydantic import BaseModel

from pirn_agents.specializations.structured_output.constrained_decoding_mapper import (
    ConstrainedDecodingMapper,
)
from pirn_agents.specializations.structured_output.structured_output_capability import (
    StructuredOutputCapability,
)
from tests.specializations.structured_output.structured_stubs import StubStructuredProvider


class _UserRecord(BaseModel):
    name: str
    age: int


def _provider(*, constrained_decoding: bool) -> StubStructuredProvider:
    return StubStructuredProvider(
        capability=StructuredOutputCapability(constrained_decoding=constrained_decoding)
    )


class TestConstraintGeneration(unittest.TestCase):
    def test_generates_json_schema_constraint(self) -> None:
        mapper = ConstrainedDecodingMapper(schema=_UserRecord)

        constraint = mapper.constraint()

        assert set(constraint["json_schema"]["properties"]) == {"name", "age"}
        assert "regex" not in constraint

    def test_generates_regex_for_string_enum(self) -> None:
        enum_schema = {"type": "string", "enum": ["red", "green", "blue"]}
        mapper = ConstrainedDecodingMapper(schema=enum_schema)

        constraint = mapper.constraint()

        assert constraint["regex"] == "^(red|green|blue)$"


class TestConstrainedDecodingMapperCapabilityGate(unittest.TestCase):
    def test_supported_provider_produces_decode_options(self) -> None:
        mapper = ConstrainedDecodingMapper(schema=_UserRecord)
        provider = _provider(constrained_decoding=True)

        options = mapper.map_request(provider)

        assert options is not None
        assert "constraint" in options["extra_body"]

    def test_unsupported_provider_skips_cleanly(self) -> None:
        mapper = ConstrainedDecodingMapper(schema=_UserRecord)
        provider = _provider(constrained_decoding=False)

        # No error — a clean skip so callers can fall back.
        assert mapper.map_request(provider) is None

    def test_rejects_non_provider(self) -> None:
        mapper = ConstrainedDecodingMapper(schema=_UserRecord)
        with self.assertRaisesRegex(TypeError, "must be a StructuredOutputProvider"):
            mapper.map_request(object())  # type: ignore[arg-type]

    def test_rejects_bad_schema(self) -> None:
        with self.assertRaisesRegex(TypeError, "schema must be"):
            ConstrainedDecodingMapper(schema=123)  # type: ignore[arg-type]


class TestConstrainedDecodingMapperGrammarValidation(unittest.TestCase):
    def test_validate_grammar_invokes_backend(self) -> None:
        fake_outlines = types.ModuleType("outlines")
        mapper = ConstrainedDecodingMapper(schema=_UserRecord, validate_grammar=True)
        provider = _provider(constrained_decoding=True)

        with mock.patch.dict(sys.modules, {"outlines": fake_outlines}):
            options = mapper.map_request(provider)

        assert options is not None
        assert "constraint" in options["extra_body"]

    def test_validate_grammar_without_backend_raises_friendly_error(self) -> None:
        mapper = ConstrainedDecodingMapper(schema=_UserRecord, validate_grammar=True)
        provider = _provider(constrained_decoding=True)

        # Simulate the backend being absent even though CI installs the extra.
        with mock.patch.dict(sys.modules, {"outlines": None}):
            with self.assertRaisesRegex(ImportError, r"pirn-agents\[grammar\]"):
                mapper.map_request(provider)


if __name__ == "__main__":
    unittest.main()
