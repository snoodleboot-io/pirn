"""Unit tests for :class:`EclipseSmspecParser`."""

from __future__ import annotations
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.reservoir.eclipse_smspec_parser import EclipseSmspecParser
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(
        self,
        smspec_path: str = "/x.smspec",
        vector_name: str = "WOPR:WELL1",
    ) -> EclipseSmspecParser:
        return EclipseSmspecParser(
            smspec_path=smspec_path,
            vector_name=vector_name,
            _config=KnotConfig(id="ep"),
        )

    async def test_rejects_empty_smspec_path(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "smspec_path"):
            await knot.process(smspec_path="", vector_name="WOPR:WELL1")

    async def test_rejects_empty_vector_name(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "vector_name"):
            await knot.process(smspec_path="/x.smspec", vector_name="")

    async def test_returns_series(self) -> None:
        knot = self._make_knot()
        out = await knot.process(smspec_path="/x.smspec", vector_name="WOPR:W1")
        assert isinstance(out, ScadaTimeSeries)
        assert out.sensor_id == "eclipse:WOPR:W1"
