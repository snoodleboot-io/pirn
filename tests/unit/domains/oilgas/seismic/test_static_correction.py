"""Unit tests for :class:`StaticCorrection`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.seismic.static_correction import StaticCorrection
from pirn.domains.oilgas.types.segy_volume import SegyVolume

_GATHER = SegyVolume(volume_id="vol")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> StaticCorrection:
        return StaticCorrection(
            gather=None,  # type: ignore[arg-type]
            datum_elevation_m=200.0,
            replacement_velocity_m_s=1800.0,
            _config=KnotConfig(id="sc", validate_io=False),
        )

    async def test_rejects_non_numeric_datum(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "datum_elevation_m"):
            await knot.process(
                gather=_GATHER,
                datum_elevation_m="hi",  # type: ignore[arg-type]
                replacement_velocity_m_s=2000.0,
            )

    async def test_rejects_non_positive_velocity(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "positive"):
            await knot.process(
                gather=_GATHER,
                datum_elevation_m=100.0,
                replacement_velocity_m_s=0.0,
            )

    async def test_returns_corrected_volume(self) -> None:
        knot = self._make_knot()
        out = await knot.process(
            gather=_GATHER,
            datum_elevation_m=200.0,
            replacement_velocity_m_s=1800.0,
        )
        assert isinstance(out, SegyVolume)
        assert out.volume_id.endswith(":static")
