"""Unit tests for :class:`ClockDriftCorrector`."""

from __future__ import annotations

import math
import unittest

import numpy as np

try:
    import scipy  # noqa: F401  # imported only to skip when scipy is absent
except ImportError as _e:
    raise unittest.SkipTest("scipy not installed") from _e

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter

from pirn_signal.resampling.clock_drift_corrector import ClockDriftCorrector
from pirn_signal.types.signal_payload import SignalPayload
from tests.conftest import make_signal_payload

_SIGNAL = make_signal_payload()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


class TestClockDriftCorrector(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> ClockDriftCorrector:
        return ClockDriftCorrector(
            signal=_up(),
            reference_rate_hz=1000.0,
            measured_rate_hz=999.5,
            _config=KnotConfig(id="cdc"),
        )

    async def test_rejects_non_positive_reference_rate(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="reference_rate_hz"):
            await knot.process(_SIGNAL, reference_rate_hz=0.0, measured_rate_hz=999.5)

    async def test_rejects_non_positive_measured_rate(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="measured_rate_hz"):
            await knot.process(_SIGNAL, reference_rate_hz=1000.0, measured_rate_hz=0.0)

    async def test_emits_signal_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, reference_rate_hz=1000.0, measured_rate_hz=999.5)
        assert isinstance(out, SignalPayload)
        assert out.metadata.signal_id == "test:drift_corrected"


class TestClockDriftCorrectorReference(unittest.IsolatedAsyncioTestCase):
    """Undo a known fractional clock drift.

    A device whose clock runs at 1000.4 Hz while labelled 1000 Hz needs a resampling
    ratio of exactly ``1000 / 1000.4 = 2500 / 2501``: ``resample_poly`` then yields
    ``ceil(N * 2500 / 2501)`` samples (scipy docs), and a tone sampled on the drifted
    clock lands on the reference clock's sample grid.
    """

    async def test_fractional_drift_is_corrected_at_the_exact_rational_ratio(self) -> None:
        # Arrange: 25 s of a 50 Hz tone sampled by a clock running at 1000.4 Hz.
        measured_rate_hz = 1000.4
        reference_rate_hz = 1000.0
        sample_count = 25010
        tone_hz = 50.0
        drifted = np.sin(2 * np.pi * tone_hz * np.arange(sample_count) / measured_rate_hz)
        payload = SignalPayload(
            metadata=make_signal_payload(
                sample_rate_hz=measured_rate_hz, samples_per_channel=sample_count
            ).metadata,
            data=drifted,
        )
        knot = ClockDriftCorrector(
            signal=_up(),
            reference_rate_hz=reference_rate_hz,
            measured_rate_hz=measured_rate_hz,
            _config=KnotConfig(id="cdc"),
        )

        # Act
        out = await knot.process(
            payload, reference_rate_hz=reference_rate_hz, measured_rate_hz=measured_rate_hz
        )

        # Assert: exact output length, and the tone sits on the 1000 Hz grid away from
        # the resampling filter's edge transients.
        assert out.data.shape[-1] == math.ceil(sample_count * 2500 / 2501)
        assert out.metadata.samples_per_channel == out.data.shape[-1]
        expected = np.sin(2 * np.pi * tone_hz * np.arange(out.data.shape[-1]) / reference_rate_hz)
        interior = slice(500, -500)
        np.testing.assert_allclose(out.data[interior], expected[interior], atol=1e-2)

    async def test_parts_per_million_drift_is_corrected_at_the_exact_ratio(self) -> None:
        # Arrange: an 8.4 ppm drift (44100.37 Hz clock labelled 44100 Hz). Its exact
        # ratio 4410000/4410037 has no small polyphase factors, and its best
        # small-denominator approximation is 1/1 — i.e. no correction at all.
        measured_rate_hz = 44100.37
        reference_rate_hz = 44100.0
        sample_count = 176_402
        tone_hz = 440.0
        drifted = np.sin(2 * np.pi * tone_hz * np.arange(sample_count) / measured_rate_hz)
        payload = SignalPayload(
            metadata=make_signal_payload(
                sample_rate_hz=measured_rate_hz, samples_per_channel=sample_count
            ).metadata,
            data=drifted,
        )
        knot = ClockDriftCorrector(
            signal=_up(),
            reference_rate_hz=reference_rate_hz,
            measured_rate_hz=measured_rate_hz,
            _config=KnotConfig(id="cdc"),
        )

        # Act
        out = await knot.process(
            payload, reference_rate_hz=reference_rate_hz, measured_rate_hz=measured_rate_hz
        )

        # Assert: 1.5 samples dropped over 4 s, and the tone is on the 44100 Hz grid at
        # the end of the recording, where an uncorrected drift is largest.
        assert out.data.shape[-1] == math.ceil(sample_count * 4_410_000 / 4_410_037)
        expected = np.sin(2 * np.pi * tone_hz * np.arange(out.data.shape[-1]) / reference_rate_hz)
        tail = slice(-2000, -100)
        np.testing.assert_allclose(out.data[tail], expected[tail], atol=1e-3)
