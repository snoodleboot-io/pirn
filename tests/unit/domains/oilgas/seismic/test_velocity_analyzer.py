"""Unit tests for :class:`VelocityAnalyzer`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.seismic.segy_file_ingester import SegyFileIngester
from pirn.domains.oilgas.seismic.velocity_analyzer import VelocityAnalyzer
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_non_numeric_velocity(self) -> None:
        with self.assertRaisesRegex(TypeError, "initial_velocity_m_s"):
            with Tapestry():
                gather = SegyFileIngester(
                    file_path="/x", volume_id="v", _config=KnotConfig(id="i")
                )
                VelocityAnalyzer(
                    gather=gather,
                    initial_velocity_m_s="fast",  # type: ignore[arg-type]
                    _config=KnotConfig(id="va"),
                )

    def test_rejects_non_positive_velocity(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive"):
            with Tapestry():
                gather = SegyFileIngester(
                    file_path="/x", volume_id="v", _config=KnotConfig(id="i")
                )
                VelocityAnalyzer(
                    gather=gather,
                    initial_velocity_m_s=-1.0,
                    _config=KnotConfig(id="va"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_initial_velocity(self) -> None:
        with Tapestry() as t:
            gather = SegyFileIngester(
                file_path="/x", volume_id="vol", _config=KnotConfig(id="i")
            )
            VelocityAnalyzer(
                gather=gather,
                initial_velocity_m_s=2200.0,
                _config=KnotConfig(id="va"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["va"] == 2200.0
