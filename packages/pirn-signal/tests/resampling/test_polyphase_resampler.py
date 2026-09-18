"""Unit tests for :class:`PolyphaseResampler`."""

from __future__ import annotations

import unittest

try:
    import scipy  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("scipy not installed") from _e

import numpy as np
import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter

from pirn_signal.resampling.polyphase_resampler import PolyphaseResampler
from pirn_signal.types.signal_payload import SignalPayload
from tests.conftest import make_signal_payload

_SIGNAL = make_signal_payload()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


class TestPolyphaseResampler(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> PolyphaseResampler:
        return PolyphaseResampler(
            signal=_up(),
            upsample_factor=3,
            downsample_factor=2,
            filter_length=32,
            _config=KnotConfig(id="pr"),
        )

    async def test_rejects_non_positive_upsample_factor(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="upsample_factor"):
            await knot.process(_SIGNAL, upsample_factor=0, downsample_factor=2, filter_length=32)

    async def test_rejects_non_positive_downsample_factor(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="downsample_factor"):
            await knot.process(_SIGNAL, upsample_factor=3, downsample_factor=0, filter_length=32)

    async def test_rejects_non_positive_filter_length(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="filter_length"):
            await knot.process(_SIGNAL, upsample_factor=3, downsample_factor=2, filter_length=0)

    async def test_emits_signal_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, upsample_factor=3, downsample_factor=2, filter_length=32)
        assert isinstance(out, SignalPayload)
        assert out.metadata.signal_id == "test:polyphase"
        assert out.metadata.sample_rate_hz == 1500.0


class TestFilterLengthIsUsed(unittest.IsolatedAsyncioTestCase):
    """``filter_length`` designs the anti-alias FIR instead of being validated only."""

    @staticmethod
    def _two_tone(sample_rate_hz: float = 4000.0, sample_count: int = 4096) -> SignalPayload:
        time = np.arange(sample_count) / sample_rate_hz
        data = np.sin(2 * np.pi * 100.0 * time) + np.sin(2 * np.pi * 1300.0 * time)
        return make_signal_payload(
            sample_rate_hz=sample_rate_hz, samples_per_channel=sample_count
        ).derive("two-tone", data)

    @staticmethod
    def _magnitude_at(data: np.ndarray, sample_rate_hz: float, target_hz: float) -> float:
        flat = np.asarray(data, dtype=float).reshape(-1)
        spectrum = np.abs(np.fft.rfft(flat))
        freqs = np.fft.rfftfreq(flat.size, d=1.0 / sample_rate_hz)
        return float(spectrum[int(np.argmin(np.abs(freqs - target_hz)))])

    def _knot(self) -> PolyphaseResampler:
        return PolyphaseResampler(
            signal=_up(),
            upsample_factor=1,
            downsample_factor=4,
            filter_length=101,
            _config=KnotConfig(id="pr"),
        )

    async def test_a_longer_filter_rejects_more_of_the_alias(self) -> None:
        payload = self._two_tone()
        knot = self._knot()

        short = await knot.process(payload, upsample_factor=1, downsample_factor=4, filter_length=7)
        long = await knot.process(
            payload, upsample_factor=1, downsample_factor=4, filter_length=301
        )

        short_alias = self._magnitude_at(short.data, 1000.0, 300.0)
        long_alias = self._magnitude_at(long.data, 1000.0, 300.0)
        assert long_alias < short_alias / 10.0, (short_alias, long_alias)

    async def test_upsampling_preserves_the_tone_amplitude(self) -> None:
        """The explicit taps carry the up-factor gain, so the tone is not attenuated."""
        sample_rate_hz = 4000.0
        sample_count = 2048
        time = np.arange(sample_count) / sample_rate_hz
        payload = make_signal_payload(
            sample_rate_hz=sample_rate_hz, samples_per_channel=sample_count
        ).derive("tone", np.sin(2 * np.pi * 100.0 * time))

        out = await self._knot().process(
            payload, upsample_factor=2, downsample_factor=1, filter_length=101
        )

        interior = np.asarray(out.data, dtype=float).reshape(-1)[200:-200]
        assert 0.9 < float(np.max(np.abs(interior))) < 1.1, float(np.max(np.abs(interior)))
