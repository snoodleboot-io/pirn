"""Round-trip and validation tests for :class:`RootFormat`."""

from __future__ import annotations
import unittest


try:
    import uproot
except ImportError as _e:
    raise unittest.SkipTest("uproot not installed") from _e

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.domains.connectors.file_formats.root_format import RootFormat
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


def _make_root_payload() -> bytes:
    """Return a minimal ROOT file containing one TTree as bytes."""
    import uproot
    import numpy as np
    import tempfile
    import os

    tmp = tempfile.mktemp(suffix=".root")
    try:
        with uproot.recreate(tmp) as f:
            f["mytree"] = {
                "x": np.array([1.0, 2.0, 3.0], dtype=np.float64),
                "y": np.array([4, 5, 6], dtype=np.int32),
            }
        with open(tmp, "rb") as fh:
            return fh.read()
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


class TestRootFormatConstruction(unittest.TestCase):
    def test_name(self) -> None:
        assert RootFormat().name == "root"

    def test_streaming_false(self) -> None:
        assert RootFormat().streaming is False

    def test_inherits_batch_file_format(self) -> None:
        assert isinstance(RootFormat(), BatchFileFormat)


class TestRootFormatRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_decode_tree(self) -> None:
        payload = _make_root_payload()
        fmt = RootFormat()
        records = await FormatRoundTrip.decode(fmt, payload)
        assert len(records) >= 1
        first = records[0]
        assert "tree_name" in first
        assert "n_entries" in first
        assert "branches" in first
        assert "data" in first
        assert isinstance(first["branches"], list)
        assert isinstance(first["data"], dict)

    async def test_decode_entries_count(self) -> None:
        payload = _make_root_payload()
        fmt = RootFormat()
        records = await FormatRoundTrip.decode(fmt, payload)
        assert len(records) >= 1
        assert records[0]["n_entries"] == 3

    async def test_decode_branch_data_bytes(self) -> None:
        import numpy as np

        payload = _make_root_payload()
        fmt = RootFormat()
        records = await FormatRoundTrip.decode(fmt, payload)
        assert len(records) >= 1
        data = records[0]["data"]
        assert "x" in data or "y" in data
        # Verify bytes can be reconstructed
        for branch_bytes in data.values():
            assert isinstance(branch_bytes, bytes)

    async def test_encode_raises_not_implemented(self) -> None:
        fmt = RootFormat()
        with self.assertRaisesRegex(NotImplementedError, "RootFormat"):
            await FormatRoundTrip.encode(fmt, [{"tree_name": "t", "n_entries": 0, "branches": [], "data": {}}])


class TestRootFormatErrors(unittest.IsolatedAsyncioTestCase):
    async def test_decode_invalid_bytes_raises(self) -> None:
        fmt = RootFormat()

        async def _bad_iter():
            yield b"not a root file at all"

        with self.assertRaises(Exception):
            record_iter = await fmt.read(_bad_iter())
            async for _ in record_iter:
                pass


class TestRootFormatMissingDep(unittest.TestCase):
    def test_import_error_message(self) -> None:
        # TODO(unittest-migrate): replace 'monkeypatch' built-in fixture — use unittest.mock.patch / assertLogs
        import builtins

        real_import = builtins.__import__

        def _block_uproot(name: str, *args: object, **kwargs: object) -> object:
            if name == "uproot":
                raise ImportError("No module named 'uproot'")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", _block_uproot)
        with self.assertRaisesRegex(ImportError, "pirn\\[physics\\]"):
            RootFormat._load_uproot()
