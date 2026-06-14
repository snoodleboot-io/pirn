"""Unit tests for :class:`VMDDecomposer`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_signal.types.wavelet_payload import WaveletPayload
from pirn_signal.wavelets.vmd_decomposer import VMDDecomposer

from tests.unit.domains.signal.conftest import emit_signal_payload


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_bare_knot(self) -> VMDDecomposer:
        with Tapestry():
            k = VMDDecomposer.__new__(VMDDecomposer)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        return k

    async def test_rejects_non_positive_mode_count(self) -> None:
        k = self._make_bare_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=None, mode_count=0, bandwidth_constraint=1.0)  # type: ignore[arg-type]

    async def test_rejects_non_positive_bandwidth(self) -> None:
        k = self._make_bare_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=None, mode_count=4, bandwidth_constraint=0)  # type: ignore[arg-type]


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_wavelet_payload(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_payload(_config=KnotConfig(id="sig"))
            VMDDecomposer(
                signal=sig,
                mode_count=4,
                bandwidth_constraint=1.0,
                _config=KnotConfig(id="w"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["w"]
        assert isinstance(out, WaveletPayload)
        assert out.frame.wavelet_name == "vmd"
        assert out.frame.scale_count == 4
        assert len(out.data) == 4
