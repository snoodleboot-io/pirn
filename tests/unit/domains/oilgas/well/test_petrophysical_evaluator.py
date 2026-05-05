"""Unit tests for :class:`PetrophysicalEvaluator`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.types.las_file import LASFile
from pirn.domains.oilgas.well.las_file_ingester import LasFileIngester
from pirn.domains.oilgas.well.petrophysical_evaluator import PetrophysicalEvaluator
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_requires_las_file_kwarg(self) -> None:
        with self.assertRaisesRegex(TypeError, "las_file"):
            PetrophysicalEvaluator(_config=KnotConfig(id="pe"))  # type: ignore[call-arg]


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_appends_interpreted_curves(self) -> None:
        with Tapestry() as t:
            las = LasFileIngester(
                file_path="/x",
                well_id="W",
                curves=("GR",),
                _config=KnotConfig(id="i"),
            )
            PetrophysicalEvaluator(
                las_file=las,
                _config=KnotConfig(id="pe"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["pe"]
        assert isinstance(out, LASFile)
        assert "VSH" in out.curves
        assert "PHIE" in out.curves
        assert "SW" in out.curves
