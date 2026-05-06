"""Unit tests for :class:`VelocityModelBuilder`."""

from __future__ import annotations

from typing import Any
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.seismic.velocity_model_builder import VelocityModelBuilder

_SEMBLANCE: list[dict[str, Any]] = [
    {"x": 0, "y": 0, "time_ms": 1000.0, "velocity_m_s": 2000.0},
    {"x": 1, "y": 0, "time_ms": 2000.0, "velocity_m_s": 2500.0},
]
_WELL_VEL: list[dict[str, Any]] = [
    {"well_id": "W-1", "depth_m": 1000.0, "velocity_m_s": 2100.0}
]


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, interpolation_method: str = "idw") -> VelocityModelBuilder:
        return VelocityModelBuilder(
            semblance_picks=None,  # type: ignore[arg-type]
            well_velocities=None,  # type: ignore[arg-type]
            interpolation_method=interpolation_method,
            _config=KnotConfig(id="vmb", validate_io=False),
        )

    async def test_rejects_invalid_interpolation_method(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "interpolation_method"):
            await knot.process(
                semblance_picks=_SEMBLANCE,
                well_velocities=_WELL_VEL,
                interpolation_method="bicubic",
            )

    async def test_returns_velocity_model(self) -> None:
        knot = self._make_knot()
        out = await knot.process(
            semblance_picks=_SEMBLANCE,
            well_velocities=_WELL_VEL,
            interpolation_method="idw",
        )
        assert out["method"] == "idw"
        assert "velocity_model" in out
        assert out["velocity_model"]["nodes"] == 3
