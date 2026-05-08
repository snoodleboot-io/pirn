"""Unit tests for :class:`EEMDDecomposer`."""

from __future__ import annotations

import unittest

import numpy as np

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.signal_payload import SignalPayload
from pirn.domains.signal.types.wavelet_payload import WaveletPayload
from pirn.domains.signal.wavelets.eemd_decomposer import EEMDDecomposer
from pirn.tapestry import Tapestry


@knot
async def emit_sine_payload_eemd() -> SignalPayload:
    """Upstream knot emitting a sinusoidal :class:`SignalPayload` for EEMD testing."""
    t = np.linspace(0, 1, 1024)
    data = np.sin(2 * np.pi * 5 * t) + 0.5 * np.sin(2 * np.pi * 20 * t)
    frame = SignalFrame(signal_id="test", channel_count=1, sample_rate_hz=1024.0, samples_per_channel=1024)
    return SignalPayload(frame=frame, data=data)


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_bare_knot(self) -> EEMDDecomposer:
        with Tapestry():
            k = EEMDDecomposer.__new__(EEMDDecomposer)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        return k

    async def test_rejects_non_positive_ensemble_size(self) -> None:
        k = self._make_bare_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=None, ensemble_size=0, noise_amplitude=0.1, max_imf_count=4)  # type: ignore[arg-type]

    async def test_rejects_non_positive_noise_amplitude(self) -> None:
        k = self._make_bare_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=None, ensemble_size=10, noise_amplitude=0, max_imf_count=4)  # type: ignore[arg-type]

    async def test_rejects_non_positive_max_imf_count(self) -> None:
        k = self._make_bare_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=None, ensemble_size=10, noise_amplitude=0.1, max_imf_count=0)  # type: ignore[arg-type]


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_wavelet_payload(self) -> None:
        with Tapestry() as t:
            sig = emit_sine_payload_eemd(_config=KnotConfig(id="sig"))
            EEMDDecomposer(
                signal=sig,
                ensemble_size=10,
                noise_amplitude=0.1,
                max_imf_count=4,
                _config=KnotConfig(id="w"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["w"]
        assert isinstance(out, WaveletPayload)
        assert out.frame.wavelet_name == "eemd"
        assert out.frame.scale_count >= 1
