"""Unit tests for :class:`ISTFTReconstructor`."""

from __future__ import annotations

import unittest

import numpy as np

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.signal.spectral.istft_reconstructor import ISTFTReconstructor
from pirn.domains.signal.types.signal_payload import SignalPayload
from pirn.domains.signal.types.spectrum_frame import SpectrumFrame
from pirn.domains.signal.types.spectrum_payload import SpectrumPayload
from pirn.tapestry import Tapestry


@knot
async def emit_spectrum_payload() -> SpectrumPayload:
    """Upstream knot emitting a deterministic SpectrumPayload."""
    # frequency_bins=33 means n_fft=(33-1)*2=64; data shape (33, n_frames)
    frame = SpectrumFrame(signal_id="stft-out", frequency_bins=33, frequency_resolution_hz=7.8)
    n_fft = (33 - 1) * 2
    n_frames = 5
    return SpectrumPayload(metadata=frame, data=np.zeros((33, n_frames), dtype=complex))


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_positive_hop_length(self) -> None:
        with Tapestry():
            k = ISTFTReconstructor.__new__(ISTFTReconstructor)
            object.__setattr__(k, "_config", KnotConfig(id="i"))
        frame = SpectrumFrame(signal_id="stft-out", frequency_bins=33, frequency_resolution_hz=7.8)
        spectrum = SpectrumPayload(metadata=frame, data=np.zeros((33, 5), dtype=complex))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(spectrum=spectrum, hop_length=0, window="hann")

    async def test_rejects_invalid_window(self) -> None:
        with Tapestry():
            k = ISTFTReconstructor.__new__(ISTFTReconstructor)
            object.__setattr__(k, "_config", KnotConfig(id="i"))
        frame = SpectrumFrame(signal_id="stft-out", frequency_bins=33, frequency_resolution_hz=7.8)
        spectrum = SpectrumPayload(metadata=frame, data=np.zeros((33, 5), dtype=complex))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(spectrum=spectrum, hop_length=64, window="rectangular")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_signal_payload(self) -> None:
        with Tapestry() as t:
            sp = emit_spectrum_payload(_config=KnotConfig(id="sp"))
            ISTFTReconstructor(
                spectrum=sp,
                hop_length=32,
                window="hann",
                _config=KnotConfig(id="i"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["i"]
        assert isinstance(out, SignalPayload)
        assert out.frame.signal_id == "stft-out:istft"
