"""Unit tests for :class:`SeismicAttributeCalculator`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.seismic.seismic_attribute_calculator import (
    SeismicAttributeCalculator,
)
from pirn.domains.oilgas.types.segy_volume import SegyVolume

_VOLUME = SegyVolume(volume_id="vol")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, attribute: str = "envelope") -> SeismicAttributeCalculator:
        return SeismicAttributeCalculator(
            volume=None,  # type: ignore[arg-type]
            attribute=attribute,
            _config=KnotConfig(id="attr", validate_io=False),
        )

    async def test_rejects_invalid_attribute(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "attribute"):
            await knot.process(volume=_VOLUME, attribute="not_real")

    async def test_returns_attribute_volume(self) -> None:
        knot = self._make_knot(attribute="rms_amplitude")
        out = await knot.process(volume=_VOLUME, attribute="rms_amplitude")
        assert isinstance(out, SegyVolume)
        assert "attr_rms_amplitude" in out.volume_id
