"""Unit tests for :class:`EclipseSmspecParser`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.reservoir.eclipse_smspec_parser import EclipseSmspecParser
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_empty_smspec_path(self) -> None:
        with self.assertRaisesRegex(ValueError, "smspec_path"):
            EclipseSmspecParser(
                smspec_path="",
                vector_name="WOPR:WELL1",
                _config=KnotConfig(id="ep"),
            )

    def test_rejects_empty_vector_name(self) -> None:
        with self.assertRaisesRegex(ValueError, "vector_name"):
            EclipseSmspecParser(
                smspec_path="/x.smspec",
                vector_name="",
                _config=KnotConfig(id="ep"),
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_series(self) -> None:
        with Tapestry() as t:
            EclipseSmspecParser(
                smspec_path="/x.smspec",
                vector_name="WOPR:W1",
                _config=KnotConfig(id="ep"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["ep"]
        assert isinstance(out, ScadaTimeSeries)
        assert out.sensor_id == "eclipse:WOPR:W1"
