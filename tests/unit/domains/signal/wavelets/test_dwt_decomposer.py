"""Unit tests for :class:`DWTDecomposer`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.types.wavelet_frame import WaveletFrame
from pirn.domains.signal.wavelets.dwt_decomposer import DWTDecomposer
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


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
    async def test_emits_wavelet_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            DWTDecomposer(
                signal=sig,
                wavelet_name="db4",
                level_count=4,
                _config=KnotConfig(id="w"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["w"]
        assert isinstance(out, WaveletFrame)
        assert out.wavelet_name == "db4"
        assert out.scale_count == 4
