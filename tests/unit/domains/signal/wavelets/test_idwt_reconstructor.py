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


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_bare_knot(self) -> IDWTReconstructor:
        with Tapestry():
            k = IDWTReconstructor.__new__(IDWTReconstructor)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        return k

    async def test_rejects_empty_wavelet(self) -> None:
        k = self._make_bare_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(wavelet_frame=None, wavelet="", level=4)  # type: ignore[arg-type]

    async def test_rejects_non_positive_level(self) -> None:
        k = self._make_bare_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(wavelet_frame=None, wavelet="db4", level=0)  # type: ignore[arg-type]


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
