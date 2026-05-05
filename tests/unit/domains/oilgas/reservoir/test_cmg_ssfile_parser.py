"""Unit tests for :class:`CmgSsfileParser`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.reservoir.cmg_ssfile_parser import CmgSsfileParser
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_empty_path(self) -> None:
        with self.assertRaisesRegex(ValueError, "ssfile_path"):
            CmgSsfileParser(
                ssfile_path="",
                vector_name="OILRATSC",
                _config=KnotConfig(id="cs"),
            )

    def test_rejects_empty_vector(self) -> None:
        with self.assertRaisesRegex(ValueError, "vector_name"):
            CmgSsfileParser(
                ssfile_path="/x",
                vector_name="",
                _config=KnotConfig(id="cs"),
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_series(self) -> None:
        with Tapestry() as t:
            CmgSsfileParser(
                ssfile_path="/x",
                vector_name="OILRATSC",
                _config=KnotConfig(id="cs"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["cs"]
        assert isinstance(out, ScadaTimeSeries)
        assert out.sensor_id == "cmg:OILRATSC"
