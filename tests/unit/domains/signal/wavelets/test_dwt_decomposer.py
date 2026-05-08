"""Unit tests for :class:`DWTDecomposer`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.types.wavelet_payload import WaveletPayload
from pirn.domains.signal.wavelets.dwt_decomposer import DWTDecomposer
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_payload


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_bare_knot(self) -> DWTDecomposer:
        with Tapestry():
            k = DWTDecomposer.__new__(DWTDecomposer)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        return k

    async def test_rejects_empty_wavelet_name(self) -> None:
        k = self._make_bare_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=None, wavelet_name="", level_count=3)  # type: ignore[arg-type]

    async def test_rejects_non_positive_level_count(self) -> None:
        k = self._make_bare_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=None, wavelet_name="db4", level_count=0)  # type: ignore[arg-type]


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_wavelet_payload(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_payload(_config=KnotConfig(id="sig"))
            DWTDecomposer(
                signal=sig,
                wavelet_name="db4",
                level_count=4,
                _config=KnotConfig(id="w"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["w"]
        assert isinstance(out, WaveletPayload)
        assert out.frame.wavelet_name == "db4"
        # pywt.wavedec with level=4 returns level+1=5 arrays: [cA4, cD4, cD3, cD2, cD1]
        assert out.frame.scale_count == 5
        assert len(out.data) == 5
