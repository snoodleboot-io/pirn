"""Unit tests for :class:`CWTDecomposer`."""

from __future__ import annotations

import unittest

try:
    import scipy  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("scipy not installed") from _e

try:
    import pywt  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("pywt not installed") from _e

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_signal.types.wavelet_payload import WaveletPayload
from pirn_signal.wavelets.cwt_decomposer import CWTDecomposer

from tests.conftest import emit_signal_payload


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_bare_knot(self) -> CWTDecomposer:
        with Tapestry():
            k = CWTDecomposer.__new__(CWTDecomposer)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        return k

    async def test_rejects_empty_wavelet_name(self) -> None:
        k = self._make_bare_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=None, wavelet_name="", scale_count=8)  # type: ignore[arg-type]

    async def test_rejects_non_positive_scale_count(self) -> None:
        k = self._make_bare_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=None, wavelet_name="morl", scale_count=0)  # type: ignore[arg-type]


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_wavelet_payload(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_payload(_config=KnotConfig(id="sig"))
            CWTDecomposer(
                signal=sig,
                wavelet_name="morl",
                scale_count=16,
                _config=KnotConfig(id="w"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["w"]
        assert isinstance(out, WaveletPayload)
        assert out.frame.wavelet_name == "morl"
        assert out.frame.scale_count == 16
        assert len(out.data) == 16
