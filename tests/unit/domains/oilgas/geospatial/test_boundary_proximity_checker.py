"""Unit tests for :class:`BoundaryProximityChecker`."""

from __future__ import annotations

from typing import Any
import unittest


from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.geospatial.boundary_proximity_checker import (
    BoundaryProximityChecker,
)
from pirn.tapestry import Tapestry


class _LocSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> dict[str, Any]:
        return {"well_id": "W", "x": 0.0, "y": 0.0}


class _BoundarySource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> dict[str, Any]:
        return {"field_id": "F1", "vertices": [], "crs": "EPSG:4326"}


class TestConstruction(unittest.TestCase):
    def test_rejects_negative_buffer(self) -> None:
        with self.assertRaisesRegex(ValueError, "buffer_distance_m"):
            with Tapestry():
                loc = _LocSource(_config=KnotConfig(id="loc"))
                bnd = _BoundarySource(_config=KnotConfig(id="bnd"))
                BoundaryProximityChecker(
                    location=loc,
                    boundary=bnd,
                    buffer_distance_m=-1.0,
                    _config=KnotConfig(id="bp"),
                )

    def test_rejects_non_numeric_buffer(self) -> None:
        with self.assertRaisesRegex(TypeError, "buffer_distance_m"):
            with Tapestry():
                loc = _LocSource(_config=KnotConfig(id="loc"))
                bnd = _BoundarySource(_config=KnotConfig(id="bnd"))
                BoundaryProximityChecker(
                    location=loc,
                    boundary=bnd,
                    buffer_distance_m="x",  # type: ignore[arg-type]
                    _config=KnotConfig(id="bp"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_check_result(self) -> None:
        with Tapestry() as t:
            loc = _LocSource(_config=KnotConfig(id="loc"))
            bnd = _BoundarySource(_config=KnotConfig(id="bnd"))
            BoundaryProximityChecker(
                location=loc,
                boundary=bnd,
                buffer_distance_m=10.0,
                _config=KnotConfig(id="bp"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["bp"]
        assert out["well_id"] == "W"
        assert out["field_id"] == "F1"
        assert out["buffer_distance_m"] == 10.0
