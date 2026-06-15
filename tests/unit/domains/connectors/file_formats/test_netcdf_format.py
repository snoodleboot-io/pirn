"""Round-trip and validation tests for :class:`NetcdfFormat`.

Note: NetCDF-4 compound types do not preserve Python ``bool``; flag-
typed fields are stored as ``int8`` and round-trip to ``int``. Tests
therefore use ``int``, ``float``, and ``str`` only.
"""

from __future__ import annotations

import unittest

try:
    import netCDF4  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("netCDF4 not installed") from _e
try:
    import numpy  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("numpy not installed") from _e

from pirn.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.connectors.file_formats.netcdf_format import (
    NetcdfFormat,
)

from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


class TestNetcdfFormatConstruction(unittest.TestCase):
    def test_default_arguments(self) -> None:
        fmt = NetcdfFormat()
        assert fmt.variable_name == "data"
        assert fmt.dimension_name == "row"
        assert fmt.compound_type_name == "record_t"
        assert fmt.field_names is None

    def test_custom_arguments(self) -> None:
        fmt = NetcdfFormat(
            variable_name="payload",
            dimension_name="idx",
            compound_type_name="my_t",
            field_names=("a", "b"),
        )
        assert fmt.variable_name == "payload"
        assert fmt.dimension_name == "idx"
        assert fmt.compound_type_name == "my_t"
        assert fmt.field_names == ("a", "b")

    def test_empty_variable_name_rejected(self) -> None:
        with self.assertRaises(ValueError):
            NetcdfFormat(variable_name="")

    def test_empty_dimension_name_rejected(self) -> None:
        with self.assertRaises(ValueError):
            NetcdfFormat(dimension_name="")

    def test_empty_compound_type_name_rejected(self) -> None:
        with self.assertRaises(ValueError):
            NetcdfFormat(compound_type_name="")

    def test_invalid_field_names_type(self) -> None:
        with self.assertRaises(TypeError):
            NetcdfFormat(field_names="ab")  # type: ignore[arg-type]

    def test_empty_field_name_rejected(self) -> None:
        with self.assertRaises(ValueError):
            NetcdfFormat(field_names=("a", ""))


class TestNetcdfFormatBasics(unittest.TestCase):
    def test_name(self) -> None:
        assert NetcdfFormat().name == "netcdf"

    def test_streaming_property(self) -> None:
        assert NetcdfFormat().streaming is False

    def test_inherits_batch_base(self) -> None:
        assert isinstance(NetcdfFormat(), BatchFileFormat)


class TestNetcdfFormatRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_basic(self) -> None:
        records = [
            {"id": 1, "name": "alpha", "score": 1.5},
            {"id": 2, "name": "beta", "score": 2.25},
            {"id": 3, "name": "gamma", "score": 3.75},
        ]
        fmt = NetcdfFormat()
        await FormatRoundTrip.assert_round_trip(fmt, records)

    async def test_round_trip_single_row(self) -> None:
        records = [{"id": 42, "name": "solo", "score": 9.0}]
        fmt = NetcdfFormat()
        await FormatRoundTrip.assert_round_trip(fmt, records)

    async def test_round_trip_custom_variable(self) -> None:
        records = [{"id": 1, "label": "x"}, {"id": 2, "label": "y"}]
        fmt = NetcdfFormat(
            variable_name="payload",
            dimension_name="rec",
            compound_type_name="cust_t",
        )
        await FormatRoundTrip.assert_round_trip(fmt, records)

    async def test_empty_payload_rejected(self) -> None:
        fmt = NetcdfFormat()
        with self.assertRaises(ValueError):
            await FormatRoundTrip.encode(fmt, [])

    async def test_decode_unknown_variable_raises(self) -> None:
        records = [{"id": 1, "label": "x"}]
        writer = NetcdfFormat(variable_name="data")
        payload = await FormatRoundTrip.encode(writer, records)
        reader = NetcdfFormat(variable_name="missing")
        with self.assertRaises(ValueError):
            await FormatRoundTrip.decode(reader, payload)
