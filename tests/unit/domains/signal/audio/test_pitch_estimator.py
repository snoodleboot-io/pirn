"""Unit tests for :class:`PitchEstimator`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.audio.pitch_estimator import PitchEstimator
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction(unittest.TestCase):
    def test_rejects_non_positive_f_min(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "f_min_hz"):
                PitchEstimator(
                    signal=sig,
                    f_min_hz=0,
                    f_max_hz=2000.0,
                    _config=KnotConfig(id="p"),
                )

    def test_rejects_f_max_le_f_min(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "f_max_hz"):
                PitchEstimator(
                    signal=sig,
                    f_min_hz=400.0,
                    f_max_hz=400.0,
                    _config=KnotConfig(id="p"),
                )

    def test_rejects_invalid_algorithm(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "algorithm"):
                PitchEstimator(
                    signal=sig,
                    f_min_hz=80.0,
                    f_max_hz=2000.0,
                    algorithm="bogus",
                    _config=KnotConfig(id="p"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_dict(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            PitchEstimator(
                signal=sig,
                f_min_hz=80.0,
                f_max_hz=2000.0,
                _config=KnotConfig(id="p"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["p"]
        assert out["algorithm"] == "yin"
        assert out["f_min_hz"] == 80.0
