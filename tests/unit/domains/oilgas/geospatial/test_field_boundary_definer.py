"""Unit tests for :class:`FieldBoundaryDefiner`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.oilgas.geospatial.field_boundary_definer import FieldBoundaryDefiner
from pirn.tapestry import Tapestry

_VERTICES = ((0.0, 0.0), (1.0, 0.0), (0.5, 1.0))


def _make_knot(
    field_id: str = "F1",
    crs: str = "EPSG:4326",
) -> FieldBoundaryDefiner:
    with Tapestry():
        verts = Parameter("verts", list, default=[], _config=KnotConfig(id="verts"))
        return FieldBoundaryDefiner(
            field_id=field_id,
            vertices=verts,
            crs=crs,
            _config=KnotConfig(id="fb"),
        )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_field_id(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "field_id"):
            await knot.process(field_id="", vertices=_VERTICES, crs="EPSG:4326")

    async def test_rejects_too_few_vertices(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "3 vertices"):
            await knot.process(
                field_id="F1",
                vertices=((0.0, 0.0), (1.0, 0.0)),
                crs="EPSG:4326",
            )

    async def test_rejects_invalid_vertex(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "vertex"):
            await knot.process(
                field_id="F1",
                vertices=((0.0, 0.0), (1.0,), (0.5, 1.0)),  # type: ignore[arg-type]
                crs="EPSG:4326",
            )

    async def test_rejects_empty_crs(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "crs"):
            await knot.process(field_id="F1", vertices=_VERTICES, crs="")

    async def test_returns_polygon_dict(self) -> None:
        knot = _make_knot()
        out = await knot.process(field_id="F1", vertices=_VERTICES, crs="EPSG:4326")
        assert out["field_id"] == "F1"
        assert out["crs"] == "EPSG:4326"
        assert out["vertex_count"] == 3
