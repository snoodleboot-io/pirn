"""Unit tests for :class:`SeismicAttributeCalculator`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.seismic.seismic_attribute_calculator import (
    SeismicAttributeCalculator,
)
from pirn.domains.oilgas.seismic.segy_file_ingester import SegyFileIngester
from pirn.domains.oilgas.types.segy_volume import SegyVolume
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_invalid_attribute(self) -> None:
        with self.assertRaisesRegex(ValueError, "attribute"):
            with Tapestry():
                volume = SegyFileIngester(
                    file_path="/x", volume_id="v", _config=KnotConfig(id="i")
                )
                SeismicAttributeCalculator(
                    volume=volume,
                    attribute="not_real",
                    _config=KnotConfig(id="attr"),
                )

    def test_accepts_envelope(self) -> None:
        with Tapestry():
            volume = SegyFileIngester(
                file_path="/x", volume_id="v", _config=KnotConfig(id="i")
            )
            calc = SeismicAttributeCalculator(
                volume=volume,
                attribute="envelope",
                _config=KnotConfig(id="attr"),
            )
            assert calc.attribute == "envelope"


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_attribute_volume(self) -> None:
        with Tapestry() as t:
            volume = SegyFileIngester(
                file_path="/x", volume_id="vol", _config=KnotConfig(id="i")
            )
            SeismicAttributeCalculator(
                volume=volume,
                attribute="rms_amplitude",
                _config=KnotConfig(id="attr"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["attr"]
        assert isinstance(out, SegyVolume)
        assert "attr_rms_amplitude" in out.volume_id
