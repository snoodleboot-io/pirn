"""Unit tests for :class:`FaultProximityAnalyzer`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.tapestry import Tapestry
from pirn_oilgas.geospatial.fault_proximity_analyzer import (
    FaultProximityAnalyzer,
)

_WELLS = [{"well_id": "W-1", "x": 0.0, "y": 0.0}]
_FAULTS = [{"fault_id": "F-1", "vertices": [[10.0, 0.0], [20.0, 0.0]]}]


def _make_knot(buffer_m: float = 500.0) -> FaultProximityAnalyzer:
    with Tapestry():
        wells = Parameter("wells", list, default=[], _config=KnotConfig(id="wells"))
        faults = Parameter("faults", list, default=[], _config=KnotConfig(id="faults"))
        return FaultProximityAnalyzer(
            wells=wells,
            faults=faults,
            buffer_m=buffer_m,
            _config=KnotConfig(id="fp"),
        )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_positive_buffer(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "buffer_m"):
            await knot.process(wells=_WELLS, faults=_FAULTS, buffer_m=0.0)

    async def test_returns_proximity_list(self) -> None:
        knot = _make_knot(buffer_m=500.0)
        out = await knot.process(wells=_WELLS, faults=_FAULTS, buffer_m=500.0)
        assert isinstance(out, list)
        assert out[0]["well_id"] == "W-1"
        assert out[0]["nearest_fault_id"] == "F-1"
        assert "distance_m" in out[0]
        assert "within_buffer" in out[0]

    async def test_within_buffer_true_when_close(self) -> None:
        knot = _make_knot(buffer_m=500.0)
        # Well at (0,0), fault segment from (10,0) to (20,0): distance = 10m
        out = await knot.process(wells=_WELLS, faults=_FAULTS, buffer_m=500.0)
        assert out[0]["within_buffer"] is True

    async def test_within_buffer_false_when_far(self) -> None:
        knot = _make_knot(buffer_m=5.0)
        # Well at (0,0), fault segment from (10,0) to (20,0): distance = 10m > 5m
        out = await knot.process(wells=_WELLS, faults=_FAULTS, buffer_m=5.0)
        assert out[0]["within_buffer"] is False
