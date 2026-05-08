"""Unit tests for :class:`SWTDecomposer`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.types.wavelet_payload import WaveletPayload
from pirn.domains.signal.wavelets.swt_decomposer import SWTDecomposer
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_payload


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_bare_knot(self) -> SWTDecomposer:
        with Tapestry():
            k = SWTDecomposer.__new__(SWTDecomposer)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        return k

    async def test_rejects_empty_wavelet(self) -> None:
        k = self._make_bare_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=None, wavelet="", level=3)  # type: ignore[arg-type]

    async def test_rejects_non_positive_level(self) -> None:
        k = self._make_bare_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=None, wavelet="db4", level=0)  # type: ignore[arg-type]


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_wavelet_payload(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_payload(_config=KnotConfig(id="sig"))
            SWTDecomposer(signal=sig, wavelet="db4", level=5, _config=KnotConfig(id="s"))
        result = await t.run(RunRequest())
        out = result.outputs["s"]
        assert isinstance(out, WaveletPayload)
        assert out.frame.wavelet_name == "db4"
        # pywt.swt with level=5 returns 5 (cA, cD) pairs → flattened to 10 arrays
        assert out.frame.scale_count == 10
        assert out.frame.signal_id == "test"
