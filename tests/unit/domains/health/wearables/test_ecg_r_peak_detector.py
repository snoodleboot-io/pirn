"""Unit tests for :class:`ECGRPeakDetector`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.types.signal_frame import SignalFrame
from pirn.domains.health.wearables.ecg_r_peak_detector import (
    ECGRPeakDetector,
)
from pirn.tapestry import Tapestry


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_signal(self) -> None:
        inst = object.__new__(ECGRPeakDetector)
        with self.assertRaisesRegex(TypeError, "SignalFrame"):
            await ECGRPeakDetector.process(
                inst,
                signal="x",  # type: ignore[arg-type]
                method="pan_tompkins",
            )

    async def test_rejects_invalid_method(self) -> None:
        inst = object.__new__(ECGRPeakDetector)
        with self.assertRaisesRegex(ValueError, "method"):
            await ECGRPeakDetector.process(
                inst,
                signal=SignalFrame(),
                method="bogus",
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_indices_tuple(self) -> None:
        with Tapestry() as t:
            ECGRPeakDetector(
                signal=SignalFrame(),
                method="pan_tompkins",
                _config=KnotConfig(id="d"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["d"]
        assert isinstance(out, tuple)
