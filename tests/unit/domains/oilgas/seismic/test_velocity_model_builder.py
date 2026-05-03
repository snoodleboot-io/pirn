"""Unit tests for :class:`VelocityModelBuilder`."""

from __future__ import annotations

from typing import Any

import pytest

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.seismic.velocity_model_builder import VelocityModelBuilder
from pirn.tapestry import Tapestry


class _SemblanceSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> list[dict[str, Any]]:
        return [
            {"x": 0, "y": 0, "time_ms": 1000.0, "velocity_m_s": 2000.0},
            {"x": 1, "y": 0, "time_ms": 2000.0, "velocity_m_s": 2500.0},
        ]


class _WellVelocitySource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> list[dict[str, Any]]:
        return [{"well_id": "W-1", "depth_m": 1000.0, "velocity_m_s": 2100.0}]


class TestConstruction:
    def test_rejects_invalid_interpolation_method(self) -> None:
        with pytest.raises(ValueError, match="interpolation_method"):
            with Tapestry():
                sp = _SemblanceSource(_config=KnotConfig(id="sp"))
                wv = _WellVelocitySource(_config=KnotConfig(id="wv"))
                VelocityModelBuilder(
                    semblance_picks=sp,
                    well_velocities=wv,
                    interpolation_method="bicubic",
                    _config=KnotConfig(id="vmb"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_velocity_model(self) -> None:
        with Tapestry() as t:
            sp = _SemblanceSource(_config=KnotConfig(id="sp"))
            wv = _WellVelocitySource(_config=KnotConfig(id="wv"))
            VelocityModelBuilder(
                semblance_picks=sp,
                well_velocities=wv,
                interpolation_method="idw",
                _config=KnotConfig(id="vmb"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["vmb"]
        assert out["method"] == "idw"
        assert "velocity_model" in out
        assert out["velocity_model"]["nodes"] == 3
