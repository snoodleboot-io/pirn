"""Round-trip and validation tests for :class:`NumpyNpzFormat`."""

from __future__ import annotations

import unittest

try:
    import numpy  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("numpy not installed") from _e

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.domains.connectors.file_formats.numpy_npz_format import (
    NumpyNpzFormat,
)
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


class TestNumpyNpzFormatConstruction(unittest.TestCase):
    def test_default_arguments(self) -> None:
        fmt = NumpyNpzFormat()
        assert fmt.array_name == "records"
        assert fmt.field_names is None

    def test_custom_array_name(self) -> None:
        fmt = NumpyNpzFormat(array_name="payload")
        assert fmt.array_name == "payload"

    def test_empty_array_name_rejected(self) -> None:
        with self.assertRaises(ValueError):
            NumpyNpzFormat(array_name="")

    def test_non_string_array_name_rejected(self) -> None:
        with self.assertRaises(ValueError):
            NumpyNpzFormat(array_name=42)  # type: ignore[arg-type]

    def test_invalid_field_names_type(self) -> None:
        with self.assertRaises(TypeError):
            NumpyNpzFormat(field_names="ab")  # type: ignore[arg-type]

    def test_empty_field_name_rejected(self) -> None:
        with self.assertRaises(ValueError):
            NumpyNpzFormat(field_names=("a", ""))


class TestNumpyNpzFormatBasics(unittest.TestCase):
    def test_name(self) -> None:
        assert NumpyNpzFormat().name == "numpy-npz"

    def test_streaming_property(self) -> None:
        assert NumpyNpzFormat().streaming is False

    def test_inherits_batch_base(self) -> None:
        assert isinstance(NumpyNpzFormat(), BatchFileFormat)


class TestNumpyNpzFormatRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_basic(self) -> None:
        records = [
            {"id": 1, "name": "alpha", "score": 1.5, "active": True},
            {"id": 2, "name": "beta", "score": 2.25, "active": False},
            {"id": 3, "name": "gamma", "score": 3.75, "active": True},
        ]
        fmt = NumpyNpzFormat()
        await FormatRoundTrip.assert_round_trip(fmt, records)

    async def test_round_trip_single_row(self) -> None:
        records = [{"id": 42, "name": "solo", "score": 9.0}]
        fmt = NumpyNpzFormat()
        await FormatRoundTrip.assert_round_trip(fmt, records)

    async def test_round_trip_custom_array_name(self) -> None:
        records = [{"id": 1, "label": "alpha"}]
        fmt = NumpyNpzFormat(array_name="payload")
        await FormatRoundTrip.assert_round_trip(fmt, records)

    async def test_empty_payload_rejected(self) -> None:
        fmt = NumpyNpzFormat()
        with self.assertRaises(ValueError):
            await FormatRoundTrip.encode(fmt, [])

    async def test_decode_missing_array_name_raises(self) -> None:
        records = [{"id": 1, "label": "x"}]
        writer = NumpyNpzFormat(array_name="records")
        payload = await FormatRoundTrip.encode(writer, records)
        reader = NumpyNpzFormat(array_name="missing")
        with self.assertRaises(ValueError):
            await FormatRoundTrip.decode(reader, payload)
