"""Unit tests for :class:`NmoCorrection`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.seismic.nmo_correction import NmoCorrection
from pirn.domains.oilgas.types.segy_volume import SegyVolume

_GATHER = SegyVolume(volume_id="vol")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> NmoCorrection:
        return NmoCorrection(
            gather=None,  # type: ignore[arg-type]
            stacking_velocity_m_s=2500.0,
            _config=KnotConfig(id="nmo", validate_io=False),
        )

    async def test_rejects_non_numeric_velocity(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "stacking_velocity_m_s"):
            await knot.process(gather=_GATHER, stacking_velocity_m_s="fast")  # type: ignore[arg-type]

    async def test_rejects_non_positive_velocity(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "positive"):
            await knot.process(gather=_GATHER, stacking_velocity_m_s=0.0)

    async def test_returns_corrected_volume(self) -> None:
        knot = self._make_knot()
        out = await knot.process(gather=_GATHER, stacking_velocity_m_s=2500.0)
        assert isinstance(out, SegyVolume)
        assert out.volume_id.endswith(":nmo")
