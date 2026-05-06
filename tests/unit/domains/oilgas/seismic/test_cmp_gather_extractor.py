"""Unit tests for :class:`CmpGatherExtractor`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.seismic.cmp_gather_extractor import CmpGatherExtractor
from pirn.domains.oilgas.types.segy_volume import SegyVolume

_VOLUME = SegyVolume(volume_id="vol")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, cmp_inline: int = 10, cmp_xline: int = 20) -> CmpGatherExtractor:
        return CmpGatherExtractor(
            volume=None,  # type: ignore[arg-type]
            cmp_inline=cmp_inline,
            cmp_xline=cmp_xline,
            _config=KnotConfig(id="cmp", validate_io=False),
        )

    async def test_rejects_negative_inline(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "cmp_inline"):
            await knot.process(volume=_VOLUME, cmp_inline=-1, cmp_xline=0)

    async def test_rejects_non_int_xline(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "cmp_xline"):
            await knot.process(volume=_VOLUME, cmp_inline=0, cmp_xline=1.5)  # type: ignore[arg-type]

    async def test_returns_subvolume(self) -> None:
        knot = self._make_knot()
        out = await knot.process(volume=_VOLUME, cmp_inline=10, cmp_xline=20)
        assert isinstance(out, SegyVolume)
        assert "cmp_10_20" in out.volume_id
