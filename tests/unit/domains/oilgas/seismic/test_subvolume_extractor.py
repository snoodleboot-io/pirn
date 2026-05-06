"""Unit tests for :class:`SubvolumeExtractor`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.seismic.subvolume_extractor import SubvolumeExtractor
from pirn.domains.oilgas.types.segy_volume import SegyVolume

_VOLUME = SegyVolume(volume_id="vol")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> SubvolumeExtractor:
        return SubvolumeExtractor(
            volume=None,  # type: ignore[arg-type]
            inline_start=0,
            inline_end=10,
            xline_start=0,
            xline_end=20,
            sample_start=0,
            sample_end=30,
            _config=KnotConfig(id="sv", validate_io=False),
        )

    async def test_rejects_negative_index(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-negative"):
            await knot.process(
                volume=_VOLUME,
                inline_start=-1,
                inline_end=10,
                xline_start=0,
                xline_end=10,
                sample_start=0,
                sample_end=10,
            )

    async def test_rejects_non_increasing_inline_range(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "inline_end"):
            await knot.process(
                volume=_VOLUME,
                inline_start=10,
                inline_end=10,
                xline_start=0,
                xline_end=10,
                sample_start=0,
                sample_end=10,
            )

    async def test_returns_sub_volume_with_dims(self) -> None:
        knot = self._make_knot()
        out = await knot.process(
            volume=_VOLUME,
            inline_start=0,
            inline_end=10,
            xline_start=0,
            xline_end=20,
            sample_start=0,
            sample_end=30,
        )
        assert isinstance(out, SegyVolume)
        assert out.inline_count == 10
        assert out.xline_count == 20
        assert out.sample_count == 30
