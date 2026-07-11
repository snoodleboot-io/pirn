"""Tests for :class:`NativeSchemaMapper` (F20-S1)."""

from __future__ import annotations

import unittest

from pydantic import BaseModel

from pirn_agents.specializations.structured_output.native_schema_mapper import (
    NativeSchemaMapper,
)
from pirn_agents.specializations.structured_output.structured_output_capability import (
    StructuredOutputCapability,
)
from tests.specializations.structured_output.structured_stubs import StubStructuredProvider


class _UserRecord(BaseModel):
    name: str
    age: int


def _provider(*, native_schema: bool) -> StubStructuredProvider:
    return StubStructuredProvider(
        capability=StructuredOutputCapability(native_schema=native_schema)
    )


class TestNativeSchemaMapperSupported(unittest.TestCase):
    def test_supported_provider_produces_native_payload(self) -> None:
        mapper = NativeSchemaMapper(schema=_UserRecord)
        provider = _provider(native_schema=True)

        options = mapper.map_request(provider)

        assert options is not None
        response_format = options["response_format"]
        assert response_format["name"] == "_UserRecord"
        assert response_format["schema"]["properties"]["name"]["type"] == "string"

    def test_raw_json_schema_target_with_explicit_name(self) -> None:
        raw_schema = {"type": "object", "properties": {"q": {"type": "string"}}}
        mapper = NativeSchemaMapper(schema=raw_schema, name="Query")
        provider = _provider(native_schema=True)

        options = mapper.map_request(provider)

        assert options is not None
        assert options["response_format"]["name"] == "Query"
        assert options["response_format"]["schema"] == raw_schema


class TestNativeSchemaMapperUnsupported(unittest.TestCase):
    def test_unsupported_provider_reports_none(self) -> None:
        mapper = NativeSchemaMapper(schema=_UserRecord)
        provider = _provider(native_schema=False)

        assert mapper.map_request(provider) is None


class TestNativeSchemaMapperValidation(unittest.TestCase):
    def test_rejects_bad_schema_type(self) -> None:
        with self.assertRaisesRegex(TypeError, "schema must be"):
            NativeSchemaMapper(schema=123)  # type: ignore[arg-type]

    def test_rejects_bad_name_type(self) -> None:
        with self.assertRaisesRegex(TypeError, "name must be"):
            NativeSchemaMapper(schema=_UserRecord, name=object())  # type: ignore[arg-type]

    def test_rejects_non_provider(self) -> None:
        mapper = NativeSchemaMapper(schema=_UserRecord)
        with self.assertRaisesRegex(TypeError, "must be a StructuredOutputProvider"):
            mapper.map_request(object())  # type: ignore[arg-type]

    def test_json_schema_derived_from_model(self) -> None:
        mapper = NativeSchemaMapper(schema=_UserRecord)

        schema = mapper.json_schema()

        assert set(schema["properties"]) == {"name", "age"}


if __name__ == "__main__":
    unittest.main()
