"""Unit tests for :class:`PeriodogramEstimator`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.spectral.periodogram_estimator import PeriodogramEstimator
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.spectrum_frame import SpectrumFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_window(self) -> None:
        with Tapestry():
            k = PeriodogramEstimator.__new__(PeriodogramEstimator)
            object.__setattr__(k, "_config", KnotConfig(id="p"))
        signal = SignalFrame(
            signal_id="test", channel_count=1, sample_rate_hz=1000.0, samples_per_channel=1024
        )
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=signal, window="")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_spectrum_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            PeriodogramEstimator(signal=sig, _config=KnotConfig(id="p"))
        result = await t.run(RunRequest())
        out = result.outputs["p"]
        assert isinstance(out, SpectrumFrame)
        assert out.signal_id == "test"
        assert out.frequency_bins == 1024 // 2 + 1
