"""Round-trip and validation tests for :class:`AacFormat`."""

from __future__ import annotations

import struct
import unittest

import pytest

try:
    import pydub
except ImportError as _e:
    raise unittest.SkipTest("pydub not installed") from _e

from pirn.domains.connectors.file_formats.aac_format import AacFormat
from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


def _pcm_record(
    sample_rate: int = 44100,
    n_channels: int = 1,
    n_frames: int = 1024,
    sample_width: int = 2,
) -> dict[str, object]:
    frames = struct.pack(
        f"<{n_frames * n_channels}h", *([0] * n_frames * n_channels)
    )
    return {
        "sample_rate": sample_rate,
        "n_channels": n_channels,
        "sample_width": sample_width,
        "n_frames": n_frames,
        "frames": frames,
    }


class TestAacFormatConstruction(unittest.TestCase):
    def test_name(self) -> None:
        assert AacFormat().name == "aac"

    def test_streaming_false(self) -> None:
        assert AacFormat().streaming is False

    def test_inherits_batch_file_format(self) -> None:
        assert isinstance(AacFormat(), BatchFileFormat)


async def _aac_round_trip(record: dict) -> list[dict]:
    """Encode then decode one record; skip if ffmpeg is absent."""
    fmt = AacFormat()
    try:
        encoded = await FormatRoundTrip.encode(fmt, [record])
        return await FormatRoundTrip.decode(fmt, encoded)
    except Exception as exc:
        if "ffmpeg" in str(exc).lower() or "avconv" in str(exc).lower():
            pytest.skip("ffmpeg not available")
        raise


class TestAacFormatRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_mono(self) -> None:
        original = _pcm_record()
        decoded = await _aac_round_trip(original)
        assert len(decoded) == 1
        # AAC is lossy — verify channel/rate metadata survive; don't compare frames.
        assert decoded[0]["sample_rate"] == original["sample_rate"]
        assert decoded[0]["n_channels"] == original["n_channels"]

    async def test_round_trip_stereo(self) -> None:
        original = _pcm_record(n_channels=2, n_frames=1024)
        decoded = await _aac_round_trip(original)
        assert len(decoded) == 1
        assert decoded[0]["sample_rate"] == original["sample_rate"]
        assert decoded[0]["n_channels"] == original["n_channels"]


class TestAacFormatErrors(unittest.IsolatedAsyncioTestCase):
    async def test_empty_payload_raises(self) -> None:
        fmt = AacFormat()

        async def _empty():
            yield b""

        with self.assertRaises((ValueError, Exception)):
            record_iter = await fmt.read(_empty())
            async for _ in record_iter:
                pass

    async def test_empty_records_raises(self) -> None:
        fmt = AacFormat()

        async def _no_records():
            return
            yield  # pragma: no cover

        with self.assertRaisesRegex(ValueError, "empty"):
            chunk_iter = await fmt.write(_no_records())
            async for _ in chunk_iter:
                pass


class TestAacFormatMissingDep(unittest.TestCase):
    def test_import_error_message(self) -> None:
        import unittest.mock
        with unittest.mock.patch.dict("sys.modules", {"pydub": None}):
            with self.assertRaisesRegex(ImportError, "pirn\\[audio\\]"):
                AacFormat._load_pydub()
