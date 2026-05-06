"""Unit tests for :class:`RMSAmplitudeWindowExtractor`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.seismic.rms_amplitude_window_extractor import (
    RMSAmplitudeWindowExtractor,
)

_VOLUME: dict[str, Any] = {"traces": []}
_HORIZON: dict[str, Any] = {
    "picks": [
        {"inline": 100, "crossline": 200, "time_ms": 1500.0},
        {"inline": 101, "crossline": 200, "time_ms": 1502.0},
    ]
}


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> RMSAmplitudeWindowExtractor:
        return RMSAmplitudeWindowExtractor(
            volume=None,  # type: ignore[arg-type]
            horizon=None,  # type: ignore[arg-type]
            window_ms_above=20.0,
            window_ms_below=20.0,
            _config=KnotConfig(id="rms", validate_io=False),
        )

    async def test_rejects_non_positive_window(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "window_ms_above"):
            await knot.process(
                volume=_VOLUME,
                horizon=_HORIZON,
                window_ms_above=0.0,
                window_ms_below=20.0,
            )

    async def test_returns_rms_map(self) -> None:
        knot = self._make_knot()
        out = await knot.process(
            volume=_VOLUME,
            horizon=_HORIZON,
            window_ms_above=20.0,
            window_ms_below=20.0,
        )
        assert "rms_map" in out
        assert len(out["rms_map"]) == 2
        assert out["window_ms"] == 40.0
