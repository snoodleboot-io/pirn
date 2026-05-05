"""Round-trip and validation tests for :class:`Netcdf4Format`."""

from __future__ import annotations
import unittest


try:
    import netCDF4
except ImportError as _e:
    raise unittest.SkipTest("netCDF4 not installed") from _e

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.domains.connectors.file_formats.netcdf4_format import Netcdf4Format
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


def _make_single_group_payload() -> bytes:
    """Return a minimal multi-group NetCDF4 file as bytes."""
    import netCDF4
    import numpy as np
    import tempfile
    import os

    tmp = tempfile.mktemp(suffix=".nc")
    try:
        ds = netCDF4.Dataset(tmp, "w", format="NETCDF4")
        try:
            ds.createDimension("x", 3)
            var = ds.createVariable("temperature", np.float32, ("x",))
            var[:] = np.array([273.15, 274.0, 275.5], dtype=np.float32)
        finally:
            ds.close()
        with open(tmp, "rb") as fh:
            return fh.read()
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def _make_multi_group_payload() -> bytes:
    """Return a NetCDF4 file with multiple groups."""
    import netCDF4
    import numpy as np
    import tempfile
    import os

    tmp = tempfile.mktemp(suffix=".nc")
    try:
        ds = netCDF4.Dataset(tmp, "w", format="NETCDF4")
        try:
            ds.createDimension("t", 2)
            root_var = ds.createVariable("time", np.float64, ("t",))
            root_var[:] = np.array([0.0, 1.0], dtype=np.float64)

            grp = ds.createGroup("sensor_a")
            grp.createDimension("n", 4)
            svar = grp.createVariable("values", np.int32, ("n",))
            svar[:] = np.array([1, 2, 3, 4], dtype=np.int32)
        finally:
            ds.close()
        with open(tmp, "rb") as fh:
            return fh.read()
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


class TestNetcdf4FormatConstruction(unittest.TestCase):
    def test_name(self) -> None:
        assert Netcdf4Format().name == "netcdf4"

    def test_streaming_false(self) -> None:
        assert Netcdf4Format().streaming is False

    def test_inherits_batch_file_format(self) -> None:
        assert isinstance(Netcdf4Format(), BatchFileFormat)


class TestNetcdf4FormatRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_decode_single_group(self) -> None:
        payload = _make_single_group_payload()
        fmt = Netcdf4Format()
        records = await FormatRoundTrip.decode(fmt, payload)
        assert len(records) >= 1
        first = records[0]
        assert "group_path" in first
        assert "variable_name" in first
        assert "dimensions" in first
        assert "shape" in first
        assert "dtype" in first
        assert "data" in first
        assert isinstance(first["data"], bytes)

    async def test_decode_multi_group(self) -> None:
        payload = _make_multi_group_payload()
        fmt = Netcdf4Format()
        records = await FormatRoundTrip.decode(fmt, payload)
        # Expect at least root var + sub-group var
        assert len(records) >= 2
        group_paths = {r["group_path"] for r in records}
        assert "/" in group_paths
        # Check sub-group is present
        sub_paths = [p for p in group_paths if p != "/"]
        assert len(sub_paths) >= 1

    async def test_encode_then_decode_round_trip(self) -> None:
        import numpy as np

        fmt = Netcdf4Format()
        records = [
            {
                "group_path": "/",
                "variable_name": "pressure",
                "dimensions": ["z"],
                "shape": (3,),
                "dtype": "float32",
                "data": np.array([1013.25, 1000.0, 900.0], dtype=np.float32).tobytes(),
            }
        ]
        encoded = await FormatRoundTrip.encode(fmt, records)
        assert isinstance(encoded, bytes)
        assert len(encoded) > 0
        decoded = await FormatRoundTrip.decode(fmt, encoded)
        assert len(decoded) == 1
        assert decoded[0]["variable_name"] == "pressure"
        assert decoded[0]["group_path"] == "/"

    async def test_encode_multi_group_round_trip(self) -> None:
        import numpy as np

        fmt = Netcdf4Format()
        records = [
            {
                "group_path": "/",
                "variable_name": "time",
                "dimensions": ["t"],
                "shape": (2,),
                "dtype": "float64",
                "data": np.array([0.0, 1.0], dtype=np.float64).tobytes(),
            },
            {
                "group_path": "/sensor_a",
                "variable_name": "readings",
                "dimensions": ["n"],
                "shape": (3,),
                "dtype": "int32",
                "data": np.array([10, 20, 30], dtype=np.int32).tobytes(),
            },
        ]
        encoded = await FormatRoundTrip.encode(fmt, records)
        decoded = await FormatRoundTrip.decode(fmt, encoded)
        assert len(decoded) == 2
        paths = {r["group_path"] for r in decoded}
        assert "/" in paths
        assert "/sensor_a" in paths


class TestNetcdf4FormatErrors(unittest.IsolatedAsyncioTestCase):
    async def test_decode_invalid_bytes_raises(self) -> None:
        fmt = Netcdf4Format()

        async def _bad_iter():
            yield b"not a netcdf4 file"

        with self.assertRaises(Exception):
            record_iter = await fmt.read(_bad_iter())
            async for _ in record_iter:
                pass


class TestNetcdf4FormatMissingDep(unittest.TestCase):
    def test_import_error_message(self) -> None:
        import builtins

        real_import = builtins.__import__

        def _block_netcdf4(name: str, *args: object, **kwargs: object) -> object:
            if name == "netCDF4":
                raise ImportError("No module named 'netCDF4'")
            return real_import(name, *args, **kwargs)

        import unittest.mock
        with unittest.mock.patch("builtins.__import__", side_effect=_block_netcdf4):
            with self.assertRaisesRegex(ImportError, "pirn\\[netcdf\\]"):
                Netcdf4Format._load_netcdf4()
