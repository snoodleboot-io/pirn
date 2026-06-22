"""Unit tests for :class:`SphericalDivergenceGain`."""

from __future__ import annotations

import unittest
from typing import Any

import pytest
from pirn.core.knot_config import KnotConfig
from pirn_oilgas.seismic.spherical_divergence_gain import (
    SphericalDivergenceGain,
)

_DATA: dict[str, Any] = {
    "traces": [
        {"samples": [1.0, 1.0, 1.0], "two_way_time_ms": 1000.0},
    ]
}


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> SphericalDivergenceGain:
        return SphericalDivergenceGain(
            data=None,  # type: ignore[arg-type]
            velocity_m_s=2000.0,
            t_power=2.0,
            _config=KnotConfig(id="sdg", validate_io=False),
        )

    async def test_rejects_non_positive_velocity(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "velocity_m_s"):
            await knot.process(data=_DATA, velocity_m_s=0.0, t_power=2.0)

    async def test_applies_gain_correction(self) -> None:
        knot = self._make_knot()
        out = await knot.process(data=_DATA, velocity_m_s=2000.0, t_power=2.0)
        assert "traces" in out
        corrected_sample = out["traces"][0]["samples"][0]
        # gain = (2000 * 1.0)^2 = 4_000_000; sample=1.0 * 4_000_000
        assert corrected_sample == pytest.approx(4_000_000.0)
