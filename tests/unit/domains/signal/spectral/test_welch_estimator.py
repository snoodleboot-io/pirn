"""Unit tests for :class:`WelchEstimator`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.spectral.welch_estimator import WelchEstimator
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.spectrum_frame import SpectrumFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_positive_segment_length(self) -> None:
        with Tapestry():
            k = WelchEstimator.__new__(WelchEstimator)
            object.__setattr__(k, "_config", KnotConfig(id="w"))
        signal = SignalFrame(
            signal_id="test", channel_count=1, sample_rate_hz=1000.0, samples_per_channel=1024
        )
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=signal, segment_length=0)

    async def test_rejects_negative_overlap(self) -> None:
        with Tapestry():
            k = WelchEstimator.__new__(WelchEstimator)
            object.__setattr__(k, "_config", KnotConfig(id="w"))
        signal = SignalFrame(
            signal_id="test", channel_count=1, sample_rate_hz=1000.0, samples_per_channel=1024
        )
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=signal, segment_length=64, overlap=-1)

    async def test_rejects_overlap_ge_segment_length(self) -> None:
        with Tapestry():
            k = WelchEstimator.__new__(WelchEstimator)
            object.__setattr__(k, "_config", KnotConfig(id="w"))
        signal = SignalFrame(
            signal_id="test", channel_count=1, sample_rate_hz=1000.0, samples_per_channel=1024
        )
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=signal, segment_length=64, overlap=64)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_spectrum_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            WelchEstimator(
                signal=sig,
                segment_length=128,
                overlap=64,
                _config=KnotConfig(id="w"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["w"]
        assert isinstance(out, SpectrumFrame)
        assert out.frequency_bins == 65
        assert out.signal_id == "test"
