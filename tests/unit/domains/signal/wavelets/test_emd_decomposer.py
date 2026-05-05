"""Unit tests for :class:`EMDDecomposer`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.types.wavelet_frame import WaveletFrame
from pirn.domains.signal.wavelets.emd_decomposer import EMDDecomposer
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction(unittest.TestCase):
    def test_rejects_non_positive_max_imf_count(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "max_imf_count"):
                EMDDecomposer(
                    signal=sig,
                    max_imf_count=0,
                    _config=KnotConfig(id="w"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_wavelet_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            EMDDecomposer(
                signal=sig,
                max_imf_count=5,
                _config=KnotConfig(id="w"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["w"]
        assert isinstance(out, WaveletFrame)
        assert out.wavelet_name == "emd"
        assert out.scale_count == 5
