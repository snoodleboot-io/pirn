"""Unit tests for :class:`DWPTDecomposer`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.types.wavelet_payload import WaveletPayload
from pirn.domains.signal.wavelets.dwpt_decomposer import DWPTDecomposer
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_payload


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_bare_knot(self) -> DWPTDecomposer:
        with Tapestry():
            k = DWPTDecomposer.__new__(DWPTDecomposer)
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
    async def test_emits_wavelet_payload_with_packet_count(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_payload(_config=KnotConfig(id="sig"))
            DWPTDecomposer(
                signal=sig,
                wavelet_name="db4",
                level_count=3,
                _config=KnotConfig(id="w"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["w"]
        assert isinstance(out, WaveletPayload)
        assert out.frame.wavelet_name == "db4"
        assert out.frame.scale_count == 8
        assert len(out.data) == 8
