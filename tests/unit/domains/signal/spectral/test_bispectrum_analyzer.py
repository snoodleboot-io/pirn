"""Unit tests for :class:`BispectrumAnalyzer`."""

from __future__ import annotations

import unittest

import numpy as np

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.spectral.bispectrum_analyzer import BispectrumAnalyzer
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
    return SignalPayload(metadata=frame, data=np.zeros(samples))


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_positive_segment_length(self) -> None:
        with Tapestry():
            k = BispectrumAnalyzer.__new__(BispectrumAnalyzer)
            object.__setattr__(k, "_config", KnotConfig(id="b"))
        signal = _make_signal_payload()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=signal, segment_length=0)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_spectrum_payload(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_payload(_config=KnotConfig(id="sig"))
            BispectrumAnalyzer(
                signal=sig,
                segment_length=128,
                _config=KnotConfig(id="b"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["b"]
        assert isinstance(out, SpectrumPayload)
        assert out.frame.frequency_bins == 65
