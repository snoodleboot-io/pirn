"""Unit tests for :class:`EMDDecomposer`."""

from __future__ import annotations

import unittest

import numpy as np

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.signal_payload import SignalPayload
from pirn.domains.signal.types.wavelet_payload import WaveletPayload
from pirn.domains.signal.wavelets.emd_decomposer import EMDDecomposer
from pirn.tapestry import Tapestry


@knot
async def emit_sine_payload() -> SignalPayload:
    """Upstream knot emitting a sinusoidal :class:`SignalPayload` for EMD testing."""
    t = np.linspace(0, 1, 1024)
    data = np.sin(2 * np.pi * 5 * t) + 0.5 * np.sin(2 * np.pi * 20 * t)
    frame = SignalFrame(signal_id="test", channel_count=1, sample_rate_hz=1024.0, samples_per_channel=1024)
    return SignalPayload(frame=frame, data=data)


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_bare_knot(self) -> EMDDecomposer:
        with Tapestry():
            k = EMDDecomposer.__new__(EMDDecomposer)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        return k

    async def test_rejects_non_positive_max_imf_count(self) -> None:
        k = self._make_bare_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=None, max_imf_count=0)  # type: ignore[arg-type]


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_wavelet_payload(self) -> None:
        with Tapestry() as t:
            sig = emit_sine_payload(_config=KnotConfig(id="sig"))
            EMDDecomposer(
                signal=sig,
                max_imf_count=5,
                _config=KnotConfig(id="w"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["w"]
        assert isinstance(out, WaveletPayload)
        assert out.frame.wavelet_name == "emd"
        assert out.frame.scale_count >= 1
