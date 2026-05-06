"""Unit tests for :class:`STFTDecomposer`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.spectral.stft_decomposer import STFTDecomposer
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.spectrum_frame import SpectrumFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_positive_window_length(self) -> None:
        with Tapestry():
            k = STFTDecomposer.__new__(STFTDecomposer)
            object.__setattr__(k, "_config", KnotConfig(id="s"))
        signal = SignalFrame(
            signal_id="test", channel_count=1, sample_rate_hz=1000.0, samples_per_channel=1024
        )
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=signal, window_length=0, hop_length=4)

    async def test_rejects_non_positive_hop_length(self) -> None:
        with Tapestry():
            k = STFTDecomposer.__new__(STFTDecomposer)
            object.__setattr__(k, "_config", KnotConfig(id="s"))
        signal = SignalFrame(
            signal_id="test", channel_count=1, sample_rate_hz=1000.0, samples_per_channel=1024
        )
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=signal, window_length=128, hop_length=0)

    async def test_rejects_hop_greater_than_window(self) -> None:
        with Tapestry():
            k = STFTDecomposer.__new__(STFTDecomposer)
            object.__setattr__(k, "_config", KnotConfig(id="s"))
        signal = SignalFrame(
            signal_id="test", channel_count=1, sample_rate_hz=1000.0, samples_per_channel=1024
        )
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=signal, window_length=64, hop_length=128)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_spectrum_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            STFTDecomposer(
                signal=sig,
                window_length=256,
                hop_length=64,
                _config=KnotConfig(id="s"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["s"]
        assert isinstance(out, SpectrumFrame)
        assert out.frequency_bins == 129
