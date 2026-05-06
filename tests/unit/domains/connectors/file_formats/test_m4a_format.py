"""Round-trip and validation tests for :class:`M4aFormat`."""

from __future__ import annotations

import struct
import unittest

import pytest

try:
    import pydub  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("pydub not installed") from _e

from pirn.domains.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.domains.connectors.file_formats.m4a_format import M4aFormat
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


class TestM4aFormatConstruction(unittest.TestCase):
    def test_name(self) -> None:
        assert M4aFormat().name == "m4a"

    def test_streaming_false(self) -> None:
        assert M4aFormat().streaming is False

    def test_inherits_batch_file_format(self) -> None:
        assert isinstance(M4aFormat(), BatchFileFormat)


class TestM4aFormatRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_mono(self) -> None:
        records = [_pcm_record()]
        try:
            await FormatRoundTrip.assert_round_trip(M4aFormat(), records)
        except Exception as exc:
            if "ffmpeg" in str(exc).lower() or "avconv" in str(exc).lower():
                pytest.skip("ffmpeg not available")
            raise

    async def test_round_trip_stereo(self) -> None:
        records = [_pcm_record(n_channels=2, n_frames=1024)]
        try:
            await FormatRoundTrip.assert_round_trip(M4aFormat(), records)
        except Exception as exc:
            if "ffmpeg" in str(exc).lower() or "avconv" in str(exc).lower():
                pytest.skip("ffmpeg not available")
            raise


class TestM4aFormatErrors(unittest.IsolatedAsyncioTestCase):
    async def test_empty_payload_raises(self) -> None:
        fmt = M4aFormat()

        async def _empty():
            yield b""

        with self.assertRaises((ValueError, Exception)):
            record_iter = await fmt.read(_empty())
            async for _ in record_iter:
                pass

    async def test_empty_records_raises(self) -> None:
        fmt = M4aFormat()

        async def _no_records():
            return
            yield  # pragma: no cover

        with self.assertRaisesRegex(ValueError, "empty"):
            chunk_iter = await fmt.write(_no_records())
            async for _ in chunk_iter:
                pass


class TestM4aFormatMissingDep(unittest.TestCase):
    def test_import_error_message(self) -> None:
        import unittest.mock
        with unittest.mock.patch.dict("sys.modules", {"pydub": None}):
            with self.assertRaisesRegex(ImportError, "pirn\\[audio\\]"):
                M4aFormat._load_pydub()
