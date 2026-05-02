"""Unit tests for :class:`WallThicknessAnalyzer`."""

from __future__ import annotations

from typing import Any

import pytest

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.integrity.wall_thickness_analyzer import (
    WallThicknessAnalyzer,
)
from pirn.tapestry import Tapestry


class _PigRunSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> dict[str, Any]:
        return {"feature_count": 5, "longest_anomaly_in": 1.0}


class TestConstruction:
    def test_rejects_non_positive_nominal(self) -> None:
        with pytest.raises(ValueError, match="nominal_thickness_in"):
            with Tapestry():
                src = _PigRunSource(_config=KnotConfig(id="src"))
                WallThicknessAnalyzer(
                    pig_run=src,
                    nominal_thickness_in=0.0,
                    minimum_allowable_thickness_in=0.2,
                    _config=KnotConfig(id="wta"),
                )

    def test_rejects_min_ge_nominal(self) -> None:
        with pytest.raises(ValueError, match="minimum_allowable_thickness_in"):
            with Tapestry():
                src = _PigRunSource(_config=KnotConfig(id="src"))
                WallThicknessAnalyzer(
                    pig_run=src,
                    nominal_thickness_in=0.5,
                    minimum_allowable_thickness_in=0.5,
                    _config=KnotConfig(id="wta"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_assessment(self) -> None:
        with Tapestry() as t:
            src = _PigRunSource(_config=KnotConfig(id="src"))
            WallThicknessAnalyzer(
                pig_run=src,
                nominal_thickness_in=0.5,
                minimum_allowable_thickness_in=0.25,
                _config=KnotConfig(id="wta"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["wta"]
        assert out["min_remaining_in"] == 0.5
        assert out["minimum_allowable_in"] == 0.25
