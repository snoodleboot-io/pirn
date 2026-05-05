"""Unit tests for :class:`FieldBoundaryDefiner`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.geospatial.field_boundary_definer import FieldBoundaryDefiner
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_empty_field_id(self) -> None:
        with self.assertRaisesRegex(ValueError, "field_id"):
            FieldBoundaryDefiner(
                field_id="",
                vertices=((0.0, 0.0), (1.0, 0.0), (0.5, 1.0)),
                crs="EPSG:4326",
                _config=KnotConfig(id="fb"),
            )

    def test_rejects_too_few_vertices(self) -> None:
        with self.assertRaisesRegex(ValueError, "3 vertices"):
            FieldBoundaryDefiner(
                field_id="F1",
                vertices=((0.0, 0.0), (1.0, 0.0)),
                crs="EPSG:4326",
                _config=KnotConfig(id="fb"),
            )

    def test_rejects_invalid_vertex(self) -> None:
        with self.assertRaisesRegex(ValueError, "vertex"):
            FieldBoundaryDefiner(
                field_id="F1",
                vertices=((0.0, 0.0), (1.0,), (0.5, 1.0)),  # type: ignore[arg-type]
                crs="EPSG:4326",
                _config=KnotConfig(id="fb"),
            )

    def test_rejects_empty_crs(self) -> None:
        with self.assertRaisesRegex(ValueError, "crs"):
            FieldBoundaryDefiner(
                field_id="F1",
                vertices=((0.0, 0.0), (1.0, 0.0), (0.5, 1.0)),
                crs="",
                _config=KnotConfig(id="fb"),
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_polygon_dict(self) -> None:
        with Tapestry() as t:
            FieldBoundaryDefiner(
                field_id="F1",
                vertices=((0.0, 0.0), (1.0, 0.0), (0.5, 1.0)),
                crs="EPSG:4326",
                _config=KnotConfig(id="fb"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["fb"]
        assert out["field_id"] == "F1"
        assert out["crs"] == "EPSG:4326"
        assert out["vertex_count"] == 3
