"""Round-trip and validation tests for :class:`WavFormat`."""

from __future__ import annotations

import struct
import unittest

from pirn.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.connectors.file_formats.wav_format import WavFormat

from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


def _pcm_record(
    sample_rate: int = 44100,
    n_channels: int = 1,
    n_frames: int = 4,
    sampwidth: int = 2,
) -> dict[str, object]:
    """Return a minimal WAV record with synthetic PCM frames."""
    # 16-bit silence frames
    frames = struct.pack(f"<{n_frames * n_channels}h", *([0] * n_frames * n_channels))
    return {
        "sample_rate": sample_rate,
        "n_channels": n_channels,
        "sampwidth": sampwidth,
        "n_frames": n_frames,
        "frames": frames,
    }


class TestWavFormatConstruction(unittest.TestCase):
    def test_name(self) -> None:
        assert WavFormat().name == "wav"

    def test_streaming_false(self) -> None:
        assert WavFormat().streaming is False

    def test_inherits_batch_file_format(self) -> None:
        assert isinstance(WavFormat(), BatchFileFormat)


class TestWavFormatRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_mono(self) -> None:
        records = [_pcm_record()]
        await FormatRoundTrip.assert_round_trip(WavFormat(), records)

    async def test_round_trip_stereo(self) -> None:
        records = [_pcm_record(n_channels=2, n_frames=8)]
        await FormatRoundTrip.assert_round_trip(WavFormat(), records)

    async def test_round_trip_higher_sample_rate(self) -> None:
        records = [_pcm_record(sample_rate=48000, n_frames=16)]
        await FormatRoundTrip.assert_round_trip(WavFormat(), records)


class TestWavFormatErrors(unittest.IsolatedAsyncioTestCase):
    async def test_empty_payload_raises(self) -> None:
        fmt = WavFormat()

        async def _empty():
            yield b""

        with self.assertRaisesRegex(ValueError, "empty"):
            record_iter = await fmt.read(_empty())
            async for _ in record_iter:
                pass

    async def test_empty_records_raises(self) -> None:
        fmt = WavFormat()

        async def _no_records():
            return
            yield  # pragma: no cover

        with self.assertRaisesRegex(ValueError, "empty"):
            chunk_iter = await fmt.write(_no_records())
            async for _ in chunk_iter:
                pass
