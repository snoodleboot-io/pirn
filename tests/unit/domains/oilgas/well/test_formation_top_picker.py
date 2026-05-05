"""Unit tests for :class:`FormationTopPicker`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.types.formation_top import FormationTop
from pirn.domains.oilgas.well.formation_top_picker import FormationTopPicker
from pirn.domains.oilgas.well.las_file_ingester import LasFileIngester
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_empty_formation_name(self) -> None:
        with self.assertRaisesRegex(ValueError, "formation_name"):
            with Tapestry():
                las = LasFileIngester(
                    file_path="/x",
                    well_id="W",
                    curves=("GR",),
                    _config=KnotConfig(id="i"),
                )
                FormationTopPicker(
                    las_file=las,
                    formation_name="",
                    depth_md=100.0,
                    _config=KnotConfig(id="ft"),
                )

    def test_rejects_negative_depth(self) -> None:
        with self.assertRaisesRegex(ValueError, "depth_md"):
            with Tapestry():
                las = LasFileIngester(
                    file_path="/x",
                    well_id="W",
                    curves=("GR",),
                    _config=KnotConfig(id="i"),
                )
                FormationTopPicker(
                    las_file=las,
                    formation_name="N",
                    depth_md=-1.0,
                    _config=KnotConfig(id="ft"),
                )

    def test_rejects_non_numeric_depth(self) -> None:
        with self.assertRaisesRegex(TypeError, "depth_md"):
            with Tapestry():
                las = LasFileIngester(
                    file_path="/x",
                    well_id="W",
                    curves=("GR",),
                    _config=KnotConfig(id="i"),
                )
                FormationTopPicker(
                    las_file=las,
                    formation_name="N",
                    depth_md="x",  # type: ignore[arg-type]
                    _config=KnotConfig(id="ft"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_formation_top(self) -> None:
        with Tapestry() as t:
            las = LasFileIngester(
                file_path="/x",
                well_id="W",
                curves=("GR",),
                _config=KnotConfig(id="i"),
            )
            FormationTopPicker(
                las_file=las,
                formation_name="Niobrara",
                depth_md=2500.0,
                _config=KnotConfig(id="ft"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["ft"]
        assert isinstance(out, FormationTop)
        assert out.formation_name == "Niobrara"
        assert out.depth_md == 2500.0
