"""Unit tests for :class:`FFTAnalyzer`."""

from __future__ import annotations

import unittest

import numpy as np
import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.spectral.fft_analyzer import FFTAnalyzer
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.signal_payload import SignalPayload
from pirn.domains.signal.types.spectrum_payload import SpectrumPayload
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_payload


def _make_signal_payload(
    signal_id: str = "test",
    sample_rate_hz: float = 1000.0,
    samples: int = 512,
) -> SignalPayload:
    frame = SignalFrame(
        signal_id=signal_id,
        channel_count=1,
        sample_rate_hz=sample_rate_hz,
        samples_per_channel=samples,
    )
    return SignalPayload(metadata=frame, data=np.zeros(samples))


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_requires_n_fft(self) -> None:
        with Tapestry():
            k = FFTAnalyzer.__new__(FFTAnalyzer)
            object.__setattr__(k, "_config", KnotConfig(id="fft"))
        signal = _make_signal_payload()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=signal)  # type: ignore[call-arg]

    async def test_rejects_non_integer_n_fft(self) -> None:
        with Tapestry():
            k = FFTAnalyzer.__new__(FFTAnalyzer)
            object.__setattr__(k, "_config", KnotConfig(id="fft"))
        signal = _make_signal_payload()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=signal, n_fft=2.5)  # type: ignore[arg-type]

    async def test_rejects_zero_n_fft(self) -> None:
        with Tapestry():
            k = FFTAnalyzer.__new__(FFTAnalyzer)
            object.__setattr__(k, "_config", KnotConfig(id="fft"))
        signal = _make_signal_payload()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=signal, n_fft=0)

    async def test_rejects_non_power_of_two(self) -> None:
        with Tapestry():
            k = FFTAnalyzer.__new__(FFTAnalyzer)
            object.__setattr__(k, "_config", KnotConfig(id="fft"))
        signal = _make_signal_payload()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=signal, n_fft=3)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_spectrum_payload(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_payload(_config=KnotConfig(id="sig"))
            FFTAnalyzer(signal=sig, n_fft=512, _config=KnotConfig(id="fft"))
        result = await t.run(RunRequest())
        out = result.outputs["fft"]
        assert isinstance(out, SpectrumPayload)
        assert out.frame.signal_id == "test"
        assert out.frame.frequency_bins == 257
        assert out.frame.frequency_resolution_hz == pytest.approx(1000.0 / 512)
        assert out.data.shape[-1] == 257
