"""Unit tests for :class:`LithologyClassifier`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.types.las_file import LASFile
from pirn.domains.oilgas.well.las_file_ingester import LasFileIngester
from pirn.domains.oilgas.well.lithology_classifier import LithologyClassifier
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_invalid_method(self) -> None:
        with self.assertRaisesRegex(ValueError, "method"):
            with Tapestry():
                las = LasFileIngester(
                    file_path="/x",
                    well_id="W",
                    curves=("GR",),
                    _config=KnotConfig(id="i"),
                )
                LithologyClassifier(
                    las_file=las,
                    method="nope",
                    _config=KnotConfig(id="lc"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_appends_lith_curve(self) -> None:
        with Tapestry() as t:
            las = LasFileIngester(
                file_path="/x",
                well_id="W",
                curves=("GR",),
                _config=KnotConfig(id="i"),
            )
            LithologyClassifier(
                las_file=las,
                method="rule_based",
                _config=KnotConfig(id="lc"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["lc"]
        assert isinstance(out, LASFile)
        assert "LITH" in out.curves
