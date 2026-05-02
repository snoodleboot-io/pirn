"""Round-trip and validation tests for :class:`AacFormat`."""

from __future__ import annotations

import struct

import pytest

pytest.importorskip("pydub")

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


class TestAacFormatConstruction:
    def test_name(self) -> None:
        assert AacFormat().name == "aac"

    def test_streaming_false(self) -> None:
        assert AacFormat().streaming is False

    def test_inherits_batch_file_format(self) -> None:
        assert isinstance(AacFormat(), BatchFileFormat)


class TestAacFormatRoundTrip:
    @pytest.mark.asyncio
    async def test_round_trip_mono(self) -> None:
        records = [_pcm_record()]
        try:
            await FormatRoundTrip.assert_round_trip(AacFormat(), records)
        except Exception as exc:
            if "ffmpeg" in str(exc).lower() or "avconv" in str(exc).lower():
                pytest.skip("ffmpeg not available")
            raise

    @pytest.mark.asyncio
    async def test_round_trip_stereo(self) -> None:
        records = [_pcm_record(n_channels=2, n_frames=1024)]
        try:
            await FormatRoundTrip.assert_round_trip(AacFormat(), records)
        except Exception as exc:
            if "ffmpeg" in str(exc).lower() or "avconv" in str(exc).lower():
                pytest.skip("ffmpeg not available")
            raise


class TestAacFormatErrors:
    @pytest.mark.asyncio
    async def test_empty_payload_raises(self) -> None:
        fmt = AacFormat()

        async def _empty():
            yield b""

        with pytest.raises((ValueError, Exception)):
            record_iter = await fmt.read(_empty())
            async for _ in record_iter:
                pass

    @pytest.mark.asyncio
    async def test_empty_records_raises(self) -> None:
        fmt = AacFormat()

        async def _no_records():
            return
            yield  # pragma: no cover

        with pytest.raises(ValueError, match="empty"):
            chunk_iter = await fmt.write(_no_records())
            async for _ in chunk_iter:
                pass


class TestAacFormatMissingDep:
    def test_import_error_message(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import builtins
        real_import = builtins.__import__

        def _mock_import(name: str, *args, **kwargs):
            if name == "pydub":
                raise ImportError("no module named pydub")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", _mock_import)
        with pytest.raises(ImportError, match="pirn\\[audio\\]"):
            AacFormat._load_pydub()
