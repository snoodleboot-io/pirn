"""Round-trip and validation tests for :class:`NumpyNpyFormat`."""

from __future__ import annotations

import unittest

try:
    import numpy  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("numpy not installed") from _e

from pirn.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.connectors.file_formats.numpy_npy_format import (
    NumpyNpyFormat,
)

from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


class TestNumpyNpyFormatConstruction(unittest.TestCase):
    def test_default_arguments(self) -> None:
        fmt = NumpyNpyFormat()
        assert fmt.field_names is None

    def test_custom_field_names(self) -> None:
        fmt = NumpyNpyFormat(field_names=("a", "b"))
        assert fmt.field_names == ("a", "b")

    def test_invalid_field_names_type(self) -> None:
        with self.assertRaises(TypeError):
            NumpyNpyFormat(field_names="ab")  # type: ignore[arg-type]

    def test_empty_field_name_rejected(self) -> None:
        with self.assertRaises(ValueError):
            NumpyNpyFormat(field_names=("a", ""))


class TestNumpyNpyFormatBasics(unittest.TestCase):
    def test_name(self) -> None:
        assert NumpyNpyFormat().name == "numpy-npy"

    def test_streaming_property(self) -> None:
        assert NumpyNpyFormat().streaming is False

    def test_inherits_batch_base(self) -> None:
        assert isinstance(NumpyNpyFormat(), BatchFileFormat)


class TestNumpyNpyFormatRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_basic(self) -> None:
        records = [
            {"id": 1, "name": "alpha", "score": 1.5, "active": True},
            {"id": 2, "name": "beta", "score": 2.25, "active": False},
            {"id": 3, "name": "gamma", "score": 3.75, "active": True},
        ]
        fmt = NumpyNpyFormat()
        await FormatRoundTrip.assert_round_trip(fmt, records)

    async def test_round_trip_single_row(self) -> None:
        records = [{"id": 42, "name": "solo", "score": 9.0}]
        fmt = NumpyNpyFormat()
        await FormatRoundTrip.assert_round_trip(fmt, records)

    async def test_empty_payload_rejected(self) -> None:
        # NPY requires a structured array; empty record stream cannot
        # produce a meaningful one with field-typed columns.
        fmt = NumpyNpyFormat()
        with self.assertRaises(ValueError):
            await FormatRoundTrip.encode(fmt, [])

    async def test_round_trip_field_names_override(self) -> None:
        records = [
            {"id": 1, "value": 10.0},
            {"id": 2, "value": 20.0},
        ]
        fmt = NumpyNpyFormat(field_names=("id", "value"))
        await FormatRoundTrip.assert_round_trip(fmt, records)
