"""Unit tests for :class:`AudioDenoiser`."""

from __future__ import annotations

import unittest

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.signal.audio.audio_denoiser import AudioDenoiser
from pirn.domains.signal.types.signal_frame import SignalFrame
from tests.unit.domains.signal.conftest import make_signal_frame

_SIGNAL = make_signal_frame()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalFrame, _config=KnotConfig(id=name))


class TestAudioDenoiser(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> AudioDenoiser:
        return AudioDenoiser(
            signal=_up(),
            noise_estimate_frames=10,
            over_subtraction_factor=1.5,
            _config=KnotConfig(id="dn"),
        )

    async def test_rejects_non_positive_noise_estimate_frames(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="noise_estimate_frames"):
            await knot.process(_SIGNAL, noise_estimate_frames=0, over_subtraction_factor=1.5)

    async def test_rejects_over_subtraction_factor_below_one(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="over_subtraction_factor"):
            await knot.process(_SIGNAL, noise_estimate_frames=10, over_subtraction_factor=0.5)

    async def test_emits_signal_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, noise_estimate_frames=10, over_subtraction_factor=1.0)
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "test:denoised"
