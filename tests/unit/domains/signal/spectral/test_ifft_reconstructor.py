"""Unit tests for :class:`IFFTReconstructor`."""

from __future__ import annotations

import unittest

import numpy as np

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.signal.spectral.ifft_reconstructor import IFFTReconstructor
from pirn.domains.signal.types.signal_payload import SignalPayload
from pirn.domains.signal.types.spectrum_frame import SpectrumFrame
from pirn.domains.signal.types.spectrum_payload import SpectrumPayload
from pirn.tapestry import Tapestry


@knot
async def emit_spectrum_payload() -> SpectrumPayload:
    """Upstream knot emitting a deterministic SpectrumPayload."""
    frame = SpectrumFrame(signal_id="spec", frequency_bins=257, frequency_resolution_hz=1.953)
    return SpectrumPayload(metadata=frame, data=np.zeros(257, dtype=complex))


class TestConstruction(unittest.TestCase):
    def test_accepts_spectrum_knot(self) -> None:
        with Tapestry():
            sp = emit_spectrum_payload(_config=KnotConfig(id="sp"))
            IFFTReconstructor(spectrum=sp, _config=KnotConfig(id="ifft"))


class TestProcessDirect(unittest.IsolatedAsyncioTestCase):
    async def test_process_returns_signal_payload_with_correct_samples(self) -> None:
        with Tapestry():
            k = IFFTReconstructor.__new__(IFFTReconstructor)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        frame = SpectrumFrame(signal_id="spec", frequency_bins=257, frequency_resolution_hz=1.953)
        spectrum = SpectrumPayload(metadata=frame, data=np.zeros(257, dtype=complex))
        result = await k.process(spectrum=spectrum)
        assert isinstance(result, SignalPayload)
        assert result.frame.signal_id == "spec:ifft"
        assert result.frame.samples_per_channel == (257 - 1) * 2
        assert result.data.shape[-1] == (257 - 1) * 2


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_signal_payload(self) -> None:
        with Tapestry() as t:
            sp = emit_spectrum_payload(_config=KnotConfig(id="sp"))
            IFFTReconstructor(spectrum=sp, _config=KnotConfig(id="ifft"))
        result = await t.run(RunRequest())
        out = result.outputs["ifft"]
        assert isinstance(out, SignalPayload)
        assert out.frame.signal_id == "spec:ifft"
        assert out.frame.samples_per_channel == (257 - 1) * 2
