"""Unit tests for :class:`AudioFileIngestor`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.audio.audio_file_ingestor import AudioFileIngestor
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_empty_path(self) -> None:
        with Tapestry():
            with self.assertRaisesRegex(ValueError, "path"):
                AudioFileIngestor(
                    path="",
                    sample_rate_hz=44100.0,
                    channel_count=1,
                    samples_per_channel=1024,
                    _config=KnotConfig(id="a"),
                )

    def test_rejects_non_positive_sample_rate(self) -> None:
        with Tapestry():
            with self.assertRaisesRegex(ValueError, "sample_rate_hz"):
                AudioFileIngestor(
                    path="/tmp/song.wav",
                    sample_rate_hz=0,
                    channel_count=1,
                    samples_per_channel=1024,
                    _config=KnotConfig(id="a"),
                )

    def test_rejects_non_positive_channel_count(self) -> None:
        with Tapestry():
            with self.assertRaisesRegex(ValueError, "channel_count"):
                AudioFileIngestor(
                    path="/tmp/song.wav",
                    sample_rate_hz=44100.0,
                    channel_count=0,
                    samples_per_channel=1024,
                    _config=KnotConfig(id="a"),
                )

    def test_rejects_negative_samples_per_channel(self) -> None:
        with Tapestry():
            with self.assertRaisesRegex(ValueError, "samples_per_channel"):
                AudioFileIngestor(
                    path="/tmp/song.wav",
                    sample_rate_hz=44100.0,
                    channel_count=1,
                    samples_per_channel=-1,
                    _config=KnotConfig(id="a"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_signal_frame_with_path_id(self) -> None:
        with Tapestry() as t:
            AudioFileIngestor(
                path="/tmp/song.wav",
                sample_rate_hz=44100.0,
                channel_count=2,
                samples_per_channel=2048,
                _config=KnotConfig(id="a"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["a"]
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "/tmp/song.wav"
        assert out.sample_rate_hz == 44100.0
        assert out.channel_count == 2
        assert out.samples_per_channel == 2048
