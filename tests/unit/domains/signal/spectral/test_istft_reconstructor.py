"""Unit tests for :class:`ISTFTReconstructor`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.signal.spectral.istft_reconstructor import ISTFTReconstructor
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.spectrum_frame import SpectrumFrame
from pirn.tapestry import Tapestry


@knot
async def emit_spectrum_frame() -> SpectrumFrame:
    """Upstream knot emitting a deterministic SpectrumFrame."""
    return SpectrumFrame(signal_id="stft-out", frequency_bins=33, frequency_resolution_hz=7.8)


class TestConstruction(unittest.TestCase):
    def test_rejects_non_positive_hop_length(self) -> None:
        with Tapestry():
            sp = emit_spectrum_frame(_config=KnotConfig(id="sp"))
            with self.assertRaisesRegex(ValueError, "hop_length"):
                ISTFTReconstructor(
                    spectrum=sp,
                    hop_length=0,
                    window="hann",
                    _config=KnotConfig(id="i"),
                )

    def test_rejects_invalid_window(self) -> None:
        with Tapestry():
            sp = emit_spectrum_frame(_config=KnotConfig(id="sp"))
            with self.assertRaisesRegex(ValueError, "window"):
                ISTFTReconstructor(
                    spectrum=sp,
                    hop_length=64,
                    window="rectangular",
                    _config=KnotConfig(id="i"),
                )

    def test_accepts_valid_params(self) -> None:
        with Tapestry():
            sp = emit_spectrum_frame(_config=KnotConfig(id="sp"))
            ISTFTReconstructor(
                spectrum=sp,
                hop_length=64,
                window="hann",
                _config=KnotConfig(id="i"),
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_signal_frame(self) -> None:
        with Tapestry() as t:
            sp = emit_spectrum_frame(_config=KnotConfig(id="sp"))
            ISTFTReconstructor(
                spectrum=sp,
                hop_length=64,
                window="hann",
                _config=KnotConfig(id="i"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["i"]
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "stft-out:istft"
        assert out.samples_per_channel == (33 - 1) * 64
