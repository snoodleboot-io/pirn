"""Unit tests for :class:`BartlettPSDEstimator`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.spectral.bartlett_psd_estimator import BartlettPSDEstimator
from pirn.domains.signal.types.spectrum_frame import SpectrumFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction(unittest.TestCase):
    def test_rejects_non_positive_num_segments(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "positive integer"):
                BartlettPSDEstimator(signal=sig, num_segments=0, _config=KnotConfig(id="b"))

    def test_accepts_valid_num_segments(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            BartlettPSDEstimator(signal=sig, num_segments=4, _config=KnotConfig(id="b"))


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_spectrum_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            BartlettPSDEstimator(signal=sig, num_segments=4, _config=KnotConfig(id="b"))
        result = await t.run(RunRequest())
        out = result.outputs["b"]
        assert isinstance(out, SpectrumFrame)
        assert out.signal_id == "test"
        assert out.frequency_bins == 1024 // 4 // 2 + 1
