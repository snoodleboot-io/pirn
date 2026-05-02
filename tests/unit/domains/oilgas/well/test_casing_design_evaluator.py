"""Unit tests for :class:`CasingDesignEvaluator`."""

from __future__ import annotations

from typing import Any

import pytest

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.types.well_path_3d import WellPath3D
from pirn.domains.oilgas.well.casing_design_evaluator import CasingDesignEvaluator
from pirn.tapestry import Tapestry


class _PathSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> WellPath3D:
        return WellPath3D(well_id="W", point_count=20)


class TestConstruction:
    def test_rejects_non_positive_burst(self) -> None:
        with pytest.raises(ValueError, match="burst_limit_psi"):
            with Tapestry():
                src = _PathSource(_config=KnotConfig(id="src"))
                CasingDesignEvaluator(
                    well_path=src,
                    burst_limit_psi=0.0,
                    collapse_limit_psi=10000.0,
                    tension_limit_lbf=200000.0,
                    _config=KnotConfig(id="cd"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_evaluation(self) -> None:
        with Tapestry() as t:
            src = _PathSource(_config=KnotConfig(id="src"))
            CasingDesignEvaluator(
                well_path=src,
                burst_limit_psi=10000.0,
                collapse_limit_psi=8000.0,
                tension_limit_lbf=300000.0,
                _config=KnotConfig(id="cd"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["cd"]
        assert out["well_id"] == "W"
        assert out["passed"] is True
