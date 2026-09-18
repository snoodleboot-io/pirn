"""Unit tests for :class:`PolyphaseDecimator`."""

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

from pirn_signal.filters.polyphase_decimator import PolyphaseDecimator
from pirn_signal.types.signal_payload import SignalPayload
from tests.conftest import make_signal_payload

_SIGNAL = make_signal_payload()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


class TestPolyphaseDecimator(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> PolyphaseDecimator:
        return PolyphaseDecimator(
            signal=_up(),
            decimation_factor=4,
            filter_taps=64,
            _config=KnotConfig(id="pd"),
        )

    async def test_rejects_decimation_factor_le_one(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="decimation_factor"):
            await knot.process(_SIGNAL, decimation_factor=1, filter_taps=64)

    async def test_rejects_non_positive_filter_taps(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="filter_taps"):
            await knot.process(_SIGNAL, decimation_factor=4, filter_taps=0)

    async def test_emits_signal_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, decimation_factor=4, filter_taps=64)
        assert isinstance(out, SignalPayload)
        assert out.metadata.signal_id == "test:polyphase-dec"


class TestFilterTapsRejectAliases(unittest.IsolatedAsyncioTestCase):
    """``filter_taps`` sets the anti-alias filter length; a short one lets aliases through."""

    @staticmethod
    def _two_tone(sample_rate_hz: float = 4000.0, sample_count: int = 4096) -> SignalPayload:
        """A 100 Hz tone to keep and a 1300 Hz tone that aliases to 300 Hz when /4."""
        time = np.arange(sample_count) / sample_rate_hz
        data = np.sin(2 * np.pi * 100.0 * time) + np.sin(2 * np.pi * 1300.0 * time)
        return make_signal_payload(
            sample_rate_hz=sample_rate_hz, samples_per_channel=sample_count
        ).derive("two-tone", data)

    @staticmethod
    def _magnitude_at(data: np.ndarray, sample_rate_hz: float, target_hz: float) -> float:
        spectrum = np.abs(np.fft.rfft(np.asarray(data, dtype=float).reshape(-1)))
        freqs = np.fft.rfftfreq(np.asarray(data).reshape(-1).size, d=1.0 / sample_rate_hz)
        return float(spectrum[int(np.argmin(np.abs(freqs - target_hz)))])

    def _knot(self) -> PolyphaseDecimator:
        return PolyphaseDecimator(
            signal=_up(),
            decimation_factor=4,
            filter_taps=101,
            _config=KnotConfig(id="pd"),
        )

    async def test_a_longer_filter_rejects_more_of_the_alias(self) -> None:
        # Arrange
        payload = self._two_tone()
        knot = self._knot()

        # Act
        short = await knot.process(payload, decimation_factor=4, filter_taps=7)
        long = await knot.process(payload, decimation_factor=4, filter_taps=301)

        # Assert: the 1300 Hz tone folds to 300 Hz in the 1000 Hz output; the long
        # filter must leave far less of it, while both keep the 100 Hz tone.
        short_alias = self._magnitude_at(short.data, 1000.0, 300.0)
        long_alias = self._magnitude_at(long.data, 1000.0, 300.0)
        assert long_alias < short_alias / 10.0, (short_alias, long_alias)
        short_signal = self._magnitude_at(short.data, 1000.0, 100.0)
        long_signal = self._magnitude_at(long.data, 1000.0, 100.0)
        assert long_signal > 0.5 * short_signal

    async def test_output_length_is_the_decimated_sample_count(self) -> None:
        payload = self._two_tone(sample_count=4096)

        out = await self._knot().process(payload, decimation_factor=4, filter_taps=101)

        assert out.data.shape[-1] == 1024
        assert out.metadata.sample_rate_hz == 1000.0
