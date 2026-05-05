"""Unit tests for :class:`SWTDecomposer`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.types.wavelet_frame import WaveletFrame
from pirn.domains.signal.wavelets.swt_decomposer import SWTDecomposer
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction(unittest.TestCase):
    def test_rejects_empty_wavelet(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "non-empty"):
                SWTDecomposer(
                    signal=sig, wavelet="", level=3, _config=KnotConfig(id="s")
                )

    def test_rejects_non_positive_level(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "level"):
                SWTDecomposer(
                    signal=sig, wavelet="db4", level=0, _config=KnotConfig(id="s")
                )

    def test_accepts_valid_params(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            SWTDecomposer(signal=sig, wavelet="haar", level=3, _config=KnotConfig(id="s"))


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_wavelet_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            SWTDecomposer(signal=sig, wavelet="db4", level=5, _config=KnotConfig(id="s"))
        result = await t.run(RunRequest())
        out = result.outputs["s"]
        assert isinstance(out, WaveletFrame)
        assert out.wavelet_name == "db4"
        assert out.scale_count == 5
        assert out.signal_id == "test"
