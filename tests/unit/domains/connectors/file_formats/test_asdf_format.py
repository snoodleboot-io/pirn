"""Round-trip and validation tests for :class:`AsdfFormat`."""

from __future__ import annotations
import unittest


try:
    import asdf
except ImportError as _e:
    raise unittest.SkipTest("asdf not installed") from _e

from pirn.domains.connectors.file_formats.asdf_format import AsdfFormat
from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


def _make_asdf_payload(tree: dict | None = None) -> bytes:
    """Return a minimal ASDF file as bytes."""
    import asdf
    import io

    if tree is None:
        tree = {"instrument": "test", "version": 1}
    af = asdf.AsdfFile(tree)
    buf = io.BytesIO()
    af.write_to(buf)
    return buf.getvalue()


class TestAsdfFormatConstruction(unittest.TestCase):
    def test_name(self) -> None:
        assert AsdfFormat().name == "asdf"

    def test_streaming_false(self) -> None:
        assert AsdfFormat().streaming is False

    def test_inherits_batch_file_format(self) -> None:
        assert isinstance(AsdfFormat(), BatchFileFormat)


class TestAsdfFormatRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_decode_simple_tree(self) -> None:
        payload = _make_asdf_payload({"answer": 42, "label": "hello"})
        fmt = AsdfFormat()
        records = await FormatRoundTrip.decode(fmt, payload)
        assert len(records) == 1
        record = records[0]
        assert isinstance(record, dict)
        assert record.get("answer") == 42

    async def test_encode_produces_valid_asdf(self) -> None:
        import asdf
        import io

        record = {"mission": "test_mission", "count": 7}
        fmt = AsdfFormat()
        payload = await FormatRoundTrip.encode(fmt, [record])
        assert isinstance(payload, bytes)
        assert len(payload) > 0
        # Verify it is a valid ASDF file
        with asdf.open(io.BytesIO(payload)) as af:
            assert isinstance(af.tree, dict)

    async def test_decode_tree_with_numeric_values(self) -> None:
        tree = {"x": 3.14, "n": 100, "flag": True}
        payload = _make_asdf_payload(tree)
        fmt = AsdfFormat()
        records = await FormatRoundTrip.decode(fmt, payload)
        assert len(records) == 1

    async def test_encode_empty_records_produces_valid_asdf(self) -> None:
        import asdf
        import io

        fmt = AsdfFormat()
        payload = await FormatRoundTrip.encode(fmt, [])
        assert isinstance(payload, bytes)
        with asdf.open(io.BytesIO(payload)) as af:
            assert isinstance(af.tree, dict)


class TestAsdfFormatErrors(unittest.IsolatedAsyncioTestCase):
    async def test_decode_invalid_bytes_raises(self) -> None:
        fmt = AsdfFormat()

        async def _bad_iter():
            yield b"not an asdf file !@#$%^&*()"

        with self.assertRaises(Exception):
            record_iter = await fmt.read(_bad_iter())
            async for _ in record_iter:
                pass


class TestAsdfFormatMissingDep(unittest.TestCase):
    def test_import_error_message(self) -> None:
        # TODO(unittest-migrate): replace 'monkeypatch' built-in fixture — use unittest.mock.patch / assertLogs
        import builtins

        real_import = builtins.__import__

        def _block_asdf(name: str, *args: object, **kwargs: object) -> object:
            if name == "asdf":
                raise ImportError("No module named 'asdf'")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", _block_asdf)
        with self.assertRaisesRegex(ImportError, "pirn\\[astronomy\\]"):
            AsdfFormat._load_asdf()
