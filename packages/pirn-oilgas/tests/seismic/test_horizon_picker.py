"""Unit tests for :class:`HorizonPicker`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn_oilgas.seismic.horizon_picker import HorizonPicker
from pirn_oilgas.types.segy_volume import SegyVolume

_VOLUME = SegyVolume(volume_id="vol")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> HorizonPicker:
        return HorizonPicker(
            volume=None,  # type: ignore[arg-type]
            horizon_name="niobrara",
            seed_inline=10,
            seed_xline=20,
            _config=KnotConfig(id="hp", validate_io=False),
        )

    async def test_rejects_empty_horizon_name(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "horizon_name"):
            await knot.process(volume=_VOLUME, horizon_name="", seed_inline=0, seed_xline=0)

    async def test_rejects_negative_seed(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "seed_inline"):
            await knot.process(volume=_VOLUME, horizon_name="top_a", seed_inline=-1, seed_xline=0)

    async def test_returns_horizon_volume(self) -> None:
        knot = self._make_knot()
        out = await knot.process(volume=_VOLUME, horizon_name="niobrara", seed_inline=10, seed_xline=20)
        assert isinstance(out, SegyVolume)
        assert "horizon_niobrara" in out.volume_id
