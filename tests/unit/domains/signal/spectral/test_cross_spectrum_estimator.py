"""Unit tests for :class:`CrossSpectrumEstimator`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.signal.spectral.cross_spectrum_estimator import (
    CrossSpectrumEstimator,
)
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.spectrum_frame import SpectrumFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import (
    emit_signal_b_frame,
    emit_signal_frame,
)


@knot
async def emit_signal_a_alt_rate() -> SignalFrame:
    return SignalFrame(
        signal_id="a",
        channel_count=1,
        sample_rate_hz=2000.0,
        samples_per_channel=1024,
    )


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_positive_segment_length(self) -> None:
        with Tapestry():
            k = CrossSpectrumEstimator.__new__(CrossSpectrumEstimator)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        signal_a = SignalFrame(
            signal_id="test", channel_count=1, sample_rate_hz=1000.0, samples_per_channel=1024
        )
        signal_b = SignalFrame(
            signal_id="other", channel_count=1, sample_rate_hz=1000.0, samples_per_channel=1024
        )
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal_a=signal_a, signal_b=signal_b, segment_length=0)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_spectrum_frame(self) -> None:
        with Tapestry() as t:
            a = emit_signal_frame(_config=KnotConfig(id="a"))
            b = emit_signal_b_frame(_config=KnotConfig(id="b"))
            CrossSpectrumEstimator(
                signal_a=a,
                signal_b=b,
                segment_length=128,
                _config=KnotConfig(id="x"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["x"]
        assert isinstance(out, SpectrumFrame)
        assert out.signal_id == "test|other"
        assert out.frequency_bins == 65

    async def test_rejects_mismatched_sample_rates(self) -> None:
        with Tapestry() as t:
            a = emit_signal_a_alt_rate(_config=KnotConfig(id="a"))
            b = emit_signal_b_frame(_config=KnotConfig(id="b"))
            CrossSpectrumEstimator(
                signal_a=a,
                signal_b=b,
                segment_length=128,
                _config=KnotConfig(id="x"),
            )
        result = await t.run(RunRequest())
        assert "x" not in result.outputs
