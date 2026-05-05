"""Unit tests for :class:`FaultDetector`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.seismic.fault_detector import FaultDetector
from pirn.domains.oilgas.seismic.segy_file_ingester import SegyFileIngester
from pirn.domains.oilgas.types.segy_volume import SegyVolume
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_non_numeric_threshold(self) -> None:
        with self.assertRaisesRegex(TypeError, "coherence_threshold"):
            with Tapestry():
                attr = SegyFileIngester(
                    file_path="/x", volume_id="v", _config=KnotConfig(id="i")
                )
                FaultDetector(
                    attribute_volume=attr,
                    coherence_threshold="x",  # type: ignore[arg-type]
                    _config=KnotConfig(id="fd"),
                )

    def test_rejects_out_of_range_threshold(self) -> None:
        with self.assertRaisesRegex(ValueError, r"\[0, 1\]"):
            with Tapestry():
                attr = SegyFileIngester(
                    file_path="/x", volume_id="v", _config=KnotConfig(id="i")
                )
                FaultDetector(
                    attribute_volume=attr,
                    coherence_threshold=2.0,
                    _config=KnotConfig(id="fd"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_fault_volume(self) -> None:
        with Tapestry() as t:
            attr = SegyFileIngester(
                file_path="/x", volume_id="vol", _config=KnotConfig(id="i")
            )
            FaultDetector(
                attribute_volume=attr,
                coherence_threshold=0.5,
                _config=KnotConfig(id="fd"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["fd"]
        assert isinstance(out, SegyVolume)
        assert out.volume_id.endswith(":faults")
