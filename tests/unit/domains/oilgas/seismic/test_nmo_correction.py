"""Unit tests for :class:`NmoCorrection`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.seismic.nmo_correction import NmoCorrection
from pirn.domains.oilgas.seismic.segy_file_ingester import SegyFileIngester
from pirn.domains.oilgas.types.segy_volume import SegyVolume
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_non_numeric_velocity(self) -> None:
        with self.assertRaisesRegex(TypeError, "stacking_velocity_m_s"):
            with Tapestry():
                gather = SegyFileIngester(
                    file_path="/x", volume_id="v", _config=KnotConfig(id="i")
                )
                NmoCorrection(
                    gather=gather,
                    stacking_velocity_m_s="fast",  # type: ignore[arg-type]
                    _config=KnotConfig(id="nmo"),
                )

    def test_rejects_non_positive_velocity(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive"):
            with Tapestry():
                gather = SegyFileIngester(
                    file_path="/x", volume_id="v", _config=KnotConfig(id="i")
                )
                NmoCorrection(
                    gather=gather,
                    stacking_velocity_m_s=0.0,
                    _config=KnotConfig(id="nmo"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_corrected_volume(self) -> None:
        with Tapestry() as t:
            gather = SegyFileIngester(
                file_path="/x", volume_id="vol", _config=KnotConfig(id="i")
            )
            NmoCorrection(
                gather=gather,
                stacking_velocity_m_s=2500.0,
                _config=KnotConfig(id="nmo"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["nmo"]
        assert isinstance(out, SegyVolume)
        assert out.volume_id.endswith(":nmo")
