"""Unit tests for :class:`CmgSsfileParser`."""

from __future__ import annotations
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.reservoir.cmg_ssfile_parser import CmgSsfileParser
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(
        self,
        ssfile_path: str = "/x",
        vector_name: str = "OILRATSC",
    ) -> CmgSsfileParser:
        return CmgSsfileParser(
            ssfile_path=ssfile_path,
            vector_name=vector_name,
            _config=KnotConfig(id="cs"),
        )

    async def test_rejects_empty_path(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "ssfile_path"):
            await knot.process(ssfile_path="", vector_name="OILRATSC")

    async def test_rejects_empty_vector(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "vector_name"):
            await knot.process(ssfile_path="/x", vector_name="")

    async def test_returns_series(self) -> None:
        knot = self._make_knot()
        out = await knot.process(ssfile_path="/x", vector_name="OILRATSC")
        assert isinstance(out, ScadaTimeSeries)
        assert out.sensor_id == "cmg:OILRATSC"
