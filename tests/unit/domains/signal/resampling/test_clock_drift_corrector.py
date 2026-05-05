"""Unit tests for :class:`ClockDriftCorrector`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.resampling.clock_drift_corrector import ClockDriftCorrector
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction(unittest.TestCase):
    def test_rejects_non_positive_reference_rate(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "reference_rate_hz"):
                ClockDriftCorrector(
                    signal=sig,
                    reference_rate_hz=0.0,
                    measured_rate_hz=1000.0,
                    _config=KnotConfig(id="cdc"),
                )

    def test_rejects_non_positive_measured_rate(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "measured_rate_hz"):
                ClockDriftCorrector(
                    signal=sig,
                    reference_rate_hz=1000.0,
                    measured_rate_hz=-5.0,
                    _config=KnotConfig(id="cdc"),
                )

    def test_valid_construction(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            cdc = ClockDriftCorrector(
                signal=sig,
                reference_rate_hz=48000.0,
                measured_rate_hz=47950.0,
                _config=KnotConfig(id="cdc"),
            )
        assert cdc.reference_rate_hz == 48000.0
        assert cdc.measured_rate_hz == 47950.0


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_corrected_signal_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            ClockDriftCorrector(
                signal=sig,
                reference_rate_hz=1000.0,
                measured_rate_hz=990.0,
                _config=KnotConfig(id="cdc"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["cdc"]
        assert isinstance(out, SignalFrame)
        assert out.sample_rate_hz == 1000.0
