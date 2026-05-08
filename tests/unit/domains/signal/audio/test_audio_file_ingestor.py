"""Unit tests for :class:`AudioFileIngestor`."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import numpy as np
import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.signal.audio.audio_file_ingestor import AudioFileIngestor
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.signal_payload import SignalPayload


def _up(name: str = "path") -> Parameter:
    return Parameter(name, str, _config=KnotConfig(id=name))


class TestAudioFileIngestor(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> AudioFileIngestor:
        return AudioFileIngestor(
            path=_up(),
            sample_rate_hz=44100.0,
            channel_count=1,
            samples_per_channel=1024,
            _config=KnotConfig(id="ingest"),
        )

    async def test_rejects_empty_path(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="path"):
            await knot.process("", sample_rate_hz=44100.0, channel_count=1, samples_per_channel=1024)

    async def test_rejects_non_positive_sample_rate(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="sample_rate_hz"):
            await knot.process("/audio.wav", sample_rate_hz=0.0, channel_count=1, samples_per_channel=1024)

    async def test_rejects_non_positive_channel_count(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="channel_count"):
            await knot.process("/audio.wav", sample_rate_hz=44100.0, channel_count=0, samples_per_channel=1024)

    async def test_emits_signal_frame(self) -> None:
        knot = self._make()
        stub = SignalPayload(
            frame=SignalFrame(
                signal_id="/audio.wav",
                channel_count=1,
                sample_rate_hz=44100.0,
                samples_per_channel=1024,
            ),
            data=np.zeros(1024),
        )
        with patch(
            "pirn.domains.signal.audio.audio_file_ingestor._load_audio",
            return_value=stub,
        ):
            out = await knot.process("/audio.wav", sample_rate_hz=44100.0, channel_count=1, samples_per_channel=1024)
        assert isinstance(out, SignalPayload)
        assert out.frame.signal_id == "/audio.wav"
        assert out.frame.sample_rate_hz == 44100.0
