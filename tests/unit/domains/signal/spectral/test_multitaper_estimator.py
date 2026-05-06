"""Unit tests for :class:`MultitaperEstimator`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.spectral.multitaper_estimator import MultitaperEstimator
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.spectrum_frame import SpectrumFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_positive_time_bandwidth(self) -> None:
        with Tapestry():
            k = MultitaperEstimator.__new__(MultitaperEstimator)
            object.__setattr__(k, "_config", KnotConfig(id="m"))
        signal = SignalFrame(
            signal_id="test", channel_count=1, sample_rate_hz=1000.0, samples_per_channel=1024
        )
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=signal, time_bandwidth=0, taper_count=4)

    async def test_rejects_non_positive_taper_count(self) -> None:
        with Tapestry():
            k = MultitaperEstimator.__new__(MultitaperEstimator)
            object.__setattr__(k, "_config", KnotConfig(id="m"))
        signal = SignalFrame(
            signal_id="test", channel_count=1, sample_rate_hz=1000.0, samples_per_channel=1024
        )
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=signal, time_bandwidth=4.0, taper_count=0)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_spectrum_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            MultitaperEstimator(
                signal=sig,
                time_bandwidth=4.0,
                taper_count=7,
                _config=KnotConfig(id="m"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["m"]
        assert isinstance(out, SpectrumFrame)
        assert out.frequency_bins == 1024 // 2 + 1
