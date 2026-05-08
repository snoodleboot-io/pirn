"""Unit tests for :class:`STFTDecomposer`."""

from __future__ import annotations

import unittest

import numpy as np

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.spectral.stft_decomposer import STFTDecomposer
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.signal_payload import SignalPayload
from pirn.domains.signal.types.spectrum_payload import SpectrumPayload
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_payload


def _make_signal_payload(samples: int = 1024) -> SignalPayload:
    frame = SignalFrame(
        signal_id="test",
        channel_count=1,
        sample_rate_hz=1000.0,
        samples_per_channel=samples,
    )
    return SignalPayload(frame=frame, data=np.zeros(samples))


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_positive_window_length(self) -> None:
        with Tapestry():
            k = STFTDecomposer.__new__(STFTDecomposer)
            object.__setattr__(k, "_config", KnotConfig(id="s"))
        signal = _make_signal_payload()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=signal, window_length=0, hop_length=4)

    async def test_rejects_non_positive_hop_length(self) -> None:
        with Tapestry():
            k = STFTDecomposer.__new__(STFTDecomposer)
            object.__setattr__(k, "_config", KnotConfig(id="s"))
        signal = _make_signal_payload()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=signal, window_length=128, hop_length=0)

    async def test_rejects_hop_greater_than_window(self) -> None:
        with Tapestry():
            k = STFTDecomposer.__new__(STFTDecomposer)
            object.__setattr__(k, "_config", KnotConfig(id="s"))
        signal = _make_signal_payload()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=signal, window_length=64, hop_length=128)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_spectrum_payload(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_payload(_config=KnotConfig(id="sig"))
            STFTDecomposer(
                signal=sig,
                window_length=256,
                hop_length=64,
                _config=KnotConfig(id="s"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["s"]
        assert isinstance(out, SpectrumPayload)
        assert out.frame.frequency_bins == 129
