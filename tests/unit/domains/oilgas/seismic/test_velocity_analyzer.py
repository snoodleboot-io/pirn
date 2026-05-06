"""Unit tests for :class:`VelocityAnalyzer`."""

from __future__ import annotations
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.seismic.velocity_analyzer import VelocityAnalyzer
from pirn.domains.oilgas.types.segy_volume import SegyVolume

_GATHER = SegyVolume(volume_id="vol")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> VelocityAnalyzer:
        return VelocityAnalyzer(
            gather=None,  # type: ignore[arg-type]
            initial_velocity_m_s=2200.0,
            _config=KnotConfig(id="va", validate_io=False),
        )

    async def test_rejects_non_numeric_velocity(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "initial_velocity_m_s"):
            await knot.process(gather=_GATHER, initial_velocity_m_s="fast")  # type: ignore[arg-type]

    async def test_rejects_non_positive_velocity(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "positive"):
            await knot.process(gather=_GATHER, initial_velocity_m_s=-1.0)

    async def test_returns_initial_velocity(self) -> None:
        knot = self._make_knot()
        out = await knot.process(gather=_GATHER, initial_velocity_m_s=2200.0)
        assert out == 2200.0
