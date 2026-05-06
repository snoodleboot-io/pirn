"""Unit tests for :class:`AudioResampler`."""

from __future__ import annotations

import unittest

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.signal.audio.audio_resampler import AudioResampler
from pirn.domains.signal.types.signal_frame import SignalFrame
from tests.unit.domains.signal.conftest import make_signal_frame

_SIGNAL = make_signal_frame()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalFrame, _config=KnotConfig(id=name))


class TestAudioResampler(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> AudioResampler:
        return AudioResampler(
            signal=_up(),
            target_sample_rate_hz=22050.0,
            _config=KnotConfig(id="rs"),
        )

    async def test_rejects_non_positive_target_rate(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="target_sample_rate_hz"):
            await knot.process(_SIGNAL, target_sample_rate_hz=0.0)

    async def test_rejects_unknown_quality(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="quality"):
            await knot.process(_SIGNAL, target_sample_rate_hz=22050.0, quality="bad")

    async def test_emits_signal_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, target_sample_rate_hz=22050.0)
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "test:resampled"
        assert out.sample_rate_hz == 22050.0
