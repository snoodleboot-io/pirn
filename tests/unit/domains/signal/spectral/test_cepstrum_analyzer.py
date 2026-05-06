"""Unit tests for :class:`CepstrumAnalyzer`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.spectral.cepstrum_analyzer import CepstrumAnalyzer
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.spectrum_frame import SpectrumFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_invalid_kind(self) -> None:
        with Tapestry():
            k = CepstrumAnalyzer.__new__(CepstrumAnalyzer)
            object.__setattr__(k, "_config", KnotConfig(id="c"))
        signal = SignalFrame(
            signal_id="test", channel_count=1, sample_rate_hz=1000.0, samples_per_channel=1024
        )
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=signal, cepstrum_kind="bogus")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_spectrum_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            CepstrumAnalyzer(signal=sig, _config=KnotConfig(id="c"))
        result = await t.run(RunRequest())
        out = result.outputs["c"]
        assert isinstance(out, SpectrumFrame)
        assert out.frequency_bins == 1024
