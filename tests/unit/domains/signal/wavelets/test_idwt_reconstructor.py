"""Unit tests for :class:`IDWTReconstructor`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.wavelet_frame import WaveletFrame
from pirn.domains.signal.wavelets.idwt_reconstructor import IDWTReconstructor
from pirn.tapestry import Tapestry


@knot
async def emit_wavelet_frame() -> WaveletFrame:
    """Upstream knot emitting a deterministic WaveletFrame."""
    return WaveletFrame(signal_id="wt", wavelet_name="db4", scale_count=4)


class TestConstruction(unittest.TestCase):
    def test_rejects_empty_wavelet(self) -> None:
        with Tapestry():
            wf = emit_wavelet_frame(_config=KnotConfig(id="wf"))
            with self.assertRaisesRegex(ValueError, "non-empty"):
                IDWTReconstructor(
                    wavelet_frame=wf, wavelet="", level=4, _config=KnotConfig(id="i")
                )

    def test_rejects_non_positive_level(self) -> None:
        with Tapestry():
            wf = emit_wavelet_frame(_config=KnotConfig(id="wf"))
            with self.assertRaisesRegex(ValueError, "level"):
                IDWTReconstructor(
                    wavelet_frame=wf, wavelet="db4", level=0, _config=KnotConfig(id="i")
                )

    def test_accepts_valid_params(self) -> None:
        with Tapestry():
            wf = emit_wavelet_frame(_config=KnotConfig(id="wf"))
            IDWTReconstructor(
                wavelet_frame=wf, wavelet="db4", level=4, _config=KnotConfig(id="i")
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_signal_frame(self) -> None:
        with Tapestry() as t:
            wf = emit_wavelet_frame(_config=KnotConfig(id="wf"))
            IDWTReconstructor(
                wavelet_frame=wf, wavelet="db4", level=4, _config=KnotConfig(id="i")
            )
        result = await t.run(RunRequest())
        out = result.outputs["i"]
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "wt:idwt"
