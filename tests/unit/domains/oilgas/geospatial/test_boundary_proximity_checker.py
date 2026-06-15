"""Unit tests for :class:`BoundaryProximityChecker`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.tapestry import Tapestry
from pirn_oilgas.geospatial.boundary_proximity_checker import (
    BoundaryProximityChecker,
)

_LOC: dict[str, Any] = {"well_id": "W", "x": 0.0, "y": 0.0}
_BOUNDARY: dict[str, Any] = {"field_id": "F1", "vertices": [], "crs": "EPSG:4326"}


def _make_knot(buffer_distance_m: float = 10.0) -> BoundaryProximityChecker:
    with Tapestry():
        loc = Parameter("loc", dict, default={}, _config=KnotConfig(id="loc"))
        bnd = Parameter("bnd", dict, default={}, _config=KnotConfig(id="bnd"))
        return BoundaryProximityChecker(
            location=loc,
            boundary=bnd,
            buffer_distance_m=buffer_distance_m,
            _config=KnotConfig(id="bp"),
        )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_negative_buffer(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "buffer_distance_m"):
            await knot.process(
                location=_LOC,
                boundary=_BOUNDARY,
                buffer_distance_m=-1.0,
            )

    async def test_rejects_non_numeric_buffer(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(TypeError, "buffer_distance_m"):
            await knot.process(
                location=_LOC,
                boundary=_BOUNDARY,
                buffer_distance_m="x",  # type: ignore[arg-type]
            )

    async def test_returns_check_result(self) -> None:
        knot = _make_knot(buffer_distance_m=10.0)
        out = await knot.process(
            location=_LOC,
            boundary=_BOUNDARY,
            buffer_distance_m=10.0,
        )
        assert out["well_id"] == "W"
        assert out["field_id"] == "F1"
        assert out["buffer_distance_m"] == 10.0

    async def test_zero_buffer_is_accepted(self) -> None:
        knot = _make_knot(buffer_distance_m=0.0)
        out = await knot.process(location=_LOC, boundary=_BOUNDARY, buffer_distance_m=0.0)
        assert out["buffer_distance_m"] == 0.0
