"""Unit tests for :class:`FKDenoisingKnot`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.seismic.fk_denoising_knot import FKDenoisingKnot

_GATHER: dict[str, Any] = {
    "traces": [
        {"offset_m": 100.0, "samples": [0.0, 1.0, 0.5]},
        {"offset_m": 200.0, "samples": [0.1, 0.9, 0.4]},
    ]
}


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> FKDenoisingKnot:
        return FKDenoisingKnot(
            gather=None,  # type: ignore[arg-type]
            velocity_threshold_m_s=1500.0,
            taper_width_pct=10.0,
            _config=KnotConfig(id="fk", validate_io=False),
        )

    async def test_rejects_non_positive_velocity(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "velocity_threshold_m_s"):
            await knot.process(gather=_GATHER, velocity_threshold_m_s=0.0, taper_width_pct=10.0)

    async def test_rejects_invalid_taper_width(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "taper_width_pct"):
            await knot.process(gather=_GATHER, velocity_threshold_m_s=1500.0, taper_width_pct=60.0)

    async def test_returns_denoised_gather(self) -> None:
        knot = self._make_knot()
        out = await knot.process(gather=_GATHER, velocity_threshold_m_s=1500.0, taper_width_pct=10.0)
        assert "denoised_traces" in out
        assert "noise_model" in out
        assert isinstance(out["denoised_traces"], list)
