"""Unit tests for :class:`FaultProximityAnalyzer`."""

from __future__ import annotations

from typing import Any

import pytest

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.geospatial.fault_proximity_analyzer import (
    FaultProximityAnalyzer,
)
from pirn.tapestry import Tapestry


class _WellsSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> list[dict[str, Any]]:
        return [{"well_id": "W-1", "x": 0.0, "y": 0.0}]


class _FaultsSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> list[dict[str, Any]]:
        return [{"fault_id": "F-1", "vertices": [[10.0, 0.0], [20.0, 0.0]]}]


class TestConstruction:
    def test_rejects_non_positive_buffer(self) -> None:
        with pytest.raises(ValueError, match="buffer_m"):
            with Tapestry():
                wells = _WellsSource(_config=KnotConfig(id="w"))
                faults = _FaultsSource(_config=KnotConfig(id="f"))
                FaultProximityAnalyzer(
                    wells=wells, faults=faults, buffer_m=0.0, _config=KnotConfig(id="fp")
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_proximity_list(self) -> None:
        with Tapestry() as t:
            wells = _WellsSource(_config=KnotConfig(id="w"))
            faults = _FaultsSource(_config=KnotConfig(id="f"))
            FaultProximityAnalyzer(
                wells=wells, faults=faults, buffer_m=500.0, _config=KnotConfig(id="fp")
            )
        result = await t.run(RunRequest())
        out = result.outputs["fp"]
        assert isinstance(out, list)
        assert out[0]["well_id"] == "W-1"
        assert out[0]["nearest_fault_id"] == "F-1"
        assert "distance_m" in out[0]
        assert "within_buffer" in out[0]
