"""Unit tests for :class:`ECGRPeakDetector`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.types.signal_frame import SignalFrame
from pirn.domains.health.wearables.ecg_r_peak_detector import (
    ECGRPeakDetector,
)
from pirn.tapestry import Tapestry


class TestConstruction:
    def test_rejects_non_signal(self) -> None:
        with pytest.raises(TypeError, match="SignalFrame"):
            ECGRPeakDetector(
                signal="x",  # type: ignore[arg-type]
                method="pan_tompkins",
                _config=KnotConfig(id="d"),
            )

    def test_rejects_invalid_method(self) -> None:
        with pytest.raises(ValueError, match="method"):
            ECGRPeakDetector(
                signal=SignalFrame(),
                method="bogus",
                _config=KnotConfig(id="d"),
            )


@pytest.mark.asyncio
class TestProcess:
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
