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
from pirn.core.knot_factory import KnotFactory
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_signal.types.signal_payload import SignalPayload
from pirn_signal.types.wavelet_frame import WaveletFrame
from pirn_signal.types.wavelet_payload import WaveletPayload
from pirn_signal.wavelets.idwt_reconstructor import IDWTReconstructor


@KnotFactory.knot
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
            IDWTReconstructor(wavelet_frame=wf, wavelet="db4", level=4, _config=KnotConfig(id="i"))
        result = await t.run(RunRequest())
        out = result.outputs["i"]
        assert isinstance(out, SignalPayload)
        assert out.metadata.signal_id == "wt:idwt"


class TestLevelMustMatchTheCoefficients(unittest.IsolatedAsyncioTestCase):
    """``level`` was validated and then ignored; waverec used the list's own depth."""

    @staticmethod
    def _payload(level: int) -> WaveletPayload:
        data = np.sin(np.linspace(0.0, 8.0, 256))
        coefficients = pywt.wavedec(data, "db4", level=level)
        return WaveletPayload(
            metadata=WaveletFrame(
                signal_id="test", wavelet_name="db4", scale_count=len(coefficients)
            ),
            data=coefficients,
        )

    @staticmethod
    def _knot() -> IDWTReconstructor:
        with Tapestry():
            knot = IDWTReconstructor.__new__(IDWTReconstructor)
            object.__setattr__(knot, "_config", KnotConfig(id="idwt"))
        return knot

    async def test_reconstructs_when_the_level_matches(self) -> None:
        out = await self._knot().process(wavelet_frame=self._payload(3), wavelet="db4", level=3)

        assert isinstance(out, SignalPayload)
        np.testing.assert_allclose(
            np.asarray(out.data)[:256], np.sin(np.linspace(0.0, 8.0, 256)), atol=1e-8
        )

    async def test_rejects_a_level_that_disagrees_with_the_payload(self) -> None:
        with self.assertRaisesRegex(ValueError, "detail band"):
            await self._knot().process(wavelet_frame=self._payload(3), wavelet="db4", level=5)
