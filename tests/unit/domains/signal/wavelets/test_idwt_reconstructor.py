"""Unit tests for :class:`IDWTReconstructor`."""

from __future__ import annotations

import unittest

try:
    import scipy  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("scipy not installed") from _e

try:
    import pywt
except ImportError as _e:
    raise unittest.SkipTest("pywt not installed") from _e

import numpy as np
import pywt
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_signal.types.signal_payload import SignalPayload
from pirn_signal.types.wavelet_frame import WaveletFrame
from pirn_signal.types.wavelet_payload import WaveletPayload
from pirn_signal.wavelets.idwt_reconstructor import IDWTReconstructor


@knot
async def emit_wavelet_payload() -> WaveletPayload:
    """Upstream knot emitting a deterministic WaveletPayload."""
    data = np.zeros(1024)
    coeffs = list(pywt.wavedec(data, "db4", level=4, axis=-1))
    frame = WaveletFrame(signal_id="wt", wavelet_name="db4", scale_count=len(coeffs))
    return WaveletPayload(metadata=frame, data=coeffs)


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
    async def test_emits_signal_payload(self) -> None:
        with Tapestry() as t:
            wf = emit_wavelet_payload(_config=KnotConfig(id="wf"))
            IDWTReconstructor(
                wavelet_frame=wf, wavelet="db4", level=4, _config=KnotConfig(id="i")
            )
        result = await t.run(RunRequest())
        out = result.outputs["i"]
        assert isinstance(out, SignalPayload)
        assert out.frame.signal_id == "wt:idwt"
