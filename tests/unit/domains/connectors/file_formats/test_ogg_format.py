"""Round-trip and validation tests for :class:`OggFormat`."""

from __future__ import annotations

import unittest

try:
    import soundfile  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("soundfile not installed") from _e
try:
    import numpy  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("numpy not installed") from _e

import numpy as np

from pirn.connectors.file_formats.batch_file_format import (
    BatchFileFormat,
)
from pirn.connectors.file_formats.ogg_format import OggFormat
from tests.unit.domains.connectors.file_formats._format_round_trip import (
    FormatRoundTrip,
)


def _pcm_record(
    sample_rate: int = 44100,
    n_channels: int = 1,
    n_frames: int = 16,
) -> dict[str, object]:
    data = np.zeros((n_frames, n_channels), dtype=np.float32)
    return {
        "sample_rate": sample_rate,
        "n_channels": n_channels,
        "n_frames": n_frames,
        "frames": data.tobytes(),
    }


class TestOggFormatConstruction(unittest.TestCase):
    def test_name(self) -> None:
        assert OggFormat().name == "ogg"

    def test_streaming_false(self) -> None:
        assert OggFormat().streaming is False

    def test_inherits_batch_file_format(self) -> None:
        assert isinstance(OggFormat(), BatchFileFormat)


class TestOggFormatRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_mono(self) -> None:
        records = [_pcm_record()]
        await FormatRoundTrip.assert_round_trip(OggFormat(), records)

    async def test_round_trip_stereo(self) -> None:
        records = [_pcm_record(n_channels=2, n_frames=32)]
        await FormatRoundTrip.assert_round_trip(OggFormat(), records)


class TestOggFormatErrors(unittest.IsolatedAsyncioTestCase):
    async def test_empty_payload_raises(self) -> None:
        fmt = OggFormat()

        async def _empty():
            yield b""

        with self.assertRaises((ValueError, Exception)):
            record_iter = await fmt.read(_empty())
            async for _ in record_iter:
                pass

    async def test_empty_records_raises(self) -> None:
        fmt = OggFormat()

        async def _no_records():
            return
            yield  # pragma: no cover

        with self.assertRaisesRegex(ValueError, "empty"):
            chunk_iter = await fmt.write(_no_records())
            async for _ in chunk_iter:
                pass


class TestOggFormatMissingDep(unittest.TestCase):
    def test_import_error_message(self) -> None:
        import builtins
        real_import = builtins.__import__

        def _mock_import(name: str, *args, **kwargs):
            if name == "soundfile":
                raise ImportError("no module named soundfile")
            return real_import(name, *args, **kwargs)

        import unittest.mock
        with unittest.mock.patch("builtins.__import__", side_effect=_mock_import):
            with self.assertRaisesRegex(ImportError, "pirn\\[audio\\]"):
                OggFormat._load_deps()
