"""Round-trip and validation tests for :class:`AvroFormat`."""

from __future__ import annotations

import unittest
from typing import Any

try:
    import fastavro  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("fastavro not installed") from _e

from pirn.connectors.file_formats.avro_format import (
    AvroFormat,
)
from pirn.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


def _explicit_schema() -> dict[str, Any]:
    return {
        "type": "record",
        "name": "AvroFixture",
        "fields": [
            {"name": "id", "type": "long"},
            {"name": "name", "type": "string"},
            {"name": "score", "type": "double"},
            {"name": "active", "type": "boolean"},
        ],
    }


class TestAvroFormatConstruction(unittest.TestCase):
    def test_default_schema_is_none(self) -> None:
        fmt = AvroFormat()
        assert fmt.schema is None

    def test_explicit_schema_is_retained(self) -> None:
        schema = _explicit_schema()
        fmt = AvroFormat(schema=schema)
        assert fmt.schema == schema

    def test_invalid_schema_type(self) -> None:
        with self.assertRaises(TypeError):
            AvroFormat(schema="not-a-dict")  # type: ignore[arg-type]


class TestAvroFormatBasics(unittest.TestCase):
    def test_name(self) -> None:
        assert AvroFormat().name == "avro"

    def test_streaming_property(self) -> None:
        assert AvroFormat().streaming is False

    def test_inherits_batch_base(self) -> None:
        assert isinstance(AvroFormat(), BatchFileFormat)


class TestAvroFormatRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_basic(self) -> None:
        records = [
            {"id": 1, "name": "alpha", "score": 1.5, "active": True},
            {"id": 2, "name": "beta", "score": 2.25, "active": False},
            {"id": 3, "name": "gamma", "score": 3.75, "active": True},
        ]
        fmt = AvroFormat(schema=_explicit_schema())
        await FormatRoundTrip.assert_round_trip(fmt, records)

    async def test_round_trip_inferred_schema(self) -> None:
        records = [
            {"id": 1, "name": "alpha", "score": 1.5, "active": True},
            {"id": 2, "name": "beta", "score": 2.25, "active": False},
        ]
        fmt = AvroFormat()
        await FormatRoundTrip.assert_round_trip(fmt, records)

    async def test_round_trip_empty_with_schema(self) -> None:
        fmt = AvroFormat(schema=_explicit_schema())
        await FormatRoundTrip.assert_round_trip(fmt, [])

    async def test_round_trip_empty_without_schema_fails(self) -> None:
        fmt = AvroFormat()
        with self.assertRaises(ValueError):
            await FormatRoundTrip.encode(fmt, [])

    async def test_round_trip_single_row(self) -> None:
        records = [
            {"id": 42, "name": "solo", "score": 9.0, "active": True}
        ]
        fmt = AvroFormat(schema=_explicit_schema())
        await FormatRoundTrip.assert_round_trip(fmt, records)
