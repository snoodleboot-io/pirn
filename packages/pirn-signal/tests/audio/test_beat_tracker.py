"""Unit tests for :class:`BeatTracker`."""

from __future__ import annotations

import unittest

try:
    import librosa  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("librosa not installed") from _e

import numpy as np
import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter

from pirn_signal.audio.beat_tracker import BeatTracker
from pirn_signal.types.feature_payload import FeaturePayload
from pirn_signal.types.signal_payload import SignalPayload
from tests.conftest import make_signal_payload

_SIGNAL = make_signal_payload()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


class TestBeatTracker(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> BeatTracker:
        return BeatTracker(
            signal=_up(),
            hop_length=512,
            _config=KnotConfig(id="bt"),
        )

    async def test_rejects_non_positive_hop_length(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="hop_length"):
            await knot.process(_SIGNAL, hop_length=0)

    async def test_rejects_non_positive_tempo_min(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="tempo_min_bpm"):
            await knot.process(_SIGNAL, hop_length=512, tempo_min_bpm=0.0)

    async def test_rejects_tempo_max_le_min(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="tempo_max_bpm"):
            await knot.process(_SIGNAL, hop_length=512, tempo_min_bpm=120.0, tempo_max_bpm=60.0)

    async def test_emits_feature_payload(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, hop_length=512)
        assert isinstance(out, FeaturePayload)
        assert out.metadata.feature_names[0] == "tempo_bpm"
        assert out.data.shape[0] == 1

    async def test_multichannel_computes_per_channel(self) -> None:
        knot = self._make()
        multichannel = make_signal_payload(channel_count=2, samples_per_channel=4096)
        out = await knot.process(multichannel, hop_length=512)
        assert isinstance(out, FeaturePayload)
        assert out.metadata.channel_count == 2
        assert out.data.shape[0] == 2


class TestTempoBandIsHonoured(unittest.IsolatedAsyncioTestCase):
    """The requested [tempo_min_bpm, tempo_max_bpm] band constrains the reported tempo."""

    @staticmethod
    def _click_train(bpm: float, seconds: float = 12.0, sample_rate_hz: float = 22050.0):
        """A metronome at ``bpm``: 5 ms clicks at exact beat positions."""
        sample_count = int(seconds * sample_rate_hz)
        data = np.zeros(sample_count)
        period = round(60.0 / bpm * sample_rate_hz)
        click = np.hanning(int(0.005 * sample_rate_hz))
        for start in range(0, sample_count - click.size, period):
            data[start : start + click.size] += click
        return make_signal_payload(
            sample_rate_hz=sample_rate_hz, samples_per_channel=sample_count
        ).derive("clicks", data)

    def _knot(self) -> BeatTracker:
        return BeatTracker(signal=_up(), hop_length=512, _config=KnotConfig(id="bt"))

    async def test_wide_band_recovers_the_generating_tempo(self) -> None:
        payload = self._click_train(120.0)

        out = await self._knot().process(
            payload, hop_length=512, tempo_min_bpm=30.0, tempo_max_bpm=240.0
        )

        # librosa's tempogram bins the tempo axis, so 120 BPM resolves to ~117.5;
        # 3 % is well inside one octave, which is what the band has to pin down.
        assert abs(float(out.data[0, 0]) - 120.0) / 120.0 < 0.03

    async def test_narrow_band_reports_the_in_band_tempo_octave(self) -> None:
        # A 120 BPM metronome analysed with a half-time band must report ~60 BPM,
        # not the 120 BPM the unconstrained tracker returns.
        payload = self._click_train(120.0)

        out = await self._knot().process(
            payload, hop_length=512, tempo_min_bpm=50.0, tempo_max_bpm=70.0
        )

        tempo = float(out.data[0, 0])
        assert 50.0 <= tempo <= 70.0, tempo
