"""Unit tests for :class:`SphericalDivergenceGain`."""

from __future__ import annotations

from typing import Any

import pytest

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.seismic.spherical_divergence_gain import (
    SphericalDivergenceGain,
)
from pirn.tapestry import Tapestry


class _DataSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> dict[str, Any]:
        return {
            "traces": [
                {"samples": [1.0, 1.0, 1.0], "two_way_time_ms": 1000.0},
            ]
        }


class TestConstruction:
    def test_rejects_non_positive_velocity(self) -> None:
        with pytest.raises(ValueError, match="velocity_m_s"):
            with Tapestry():
                src = _DataSource(_config=KnotConfig(id="src"))
                SphericalDivergenceGain(
                    data=src,
                    velocity_m_s=0.0,
                    _config=KnotConfig(id="sdg"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_applies_gain_correction(self) -> None:
        with Tapestry() as t:
            src = _DataSource(_config=KnotConfig(id="src"))
            SphericalDivergenceGain(
                data=src,
                velocity_m_s=2000.0,
                t_power=2.0,
                _config=KnotConfig(id="sdg"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["sdg"]
        assert "traces" in out
        corrected_sample = out["traces"][0]["samples"][0]
        # gain = (2000 * 1.0)^2 = 4_000_000; sample=1.0 * 4_000_000
        assert corrected_sample == pytest.approx(4_000_000.0)
