"""Unit tests for :class:`SegyFileIngester`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.seismic.segy_file_ingester import SegyFileIngester
from pirn.domains.oilgas.types.segy_volume import SegyVolume


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> SegyFileIngester:
        return SegyFileIngester(
            file_path="/data/x.sgy",
            volume_id="vol-1",
            _config=KnotConfig(id="ingest"),
        )

    async def test_rejects_empty_file_path(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "file_path"):
            await knot.process(file_path="", volume_id="vol")

    async def test_rejects_non_string_file_path(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "file_path"):
            await knot.process(file_path=42, volume_id="vol")  # type: ignore[arg-type]

    async def test_rejects_empty_volume_id(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "volume_id"):
            await knot.process(file_path="/data/x.sgy", volume_id="")

    async def test_returns_typed_volume(self) -> None:
        knot = self._make_knot()
        out = await knot.process(file_path="/data/x.sgy", volume_id="vol-1")
        assert isinstance(out, SegyVolume)
        assert out.volume_id == "vol-1"
