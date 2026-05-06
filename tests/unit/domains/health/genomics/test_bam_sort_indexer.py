"""Unit tests for :class:`BAMSortIndexer`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.health.genomics.bam_sort_indexer import BAMSortIndexer
from pirn.tapestry import Tapestry

_CFG = KnotConfig(id="b")


def _make_knot() -> BAMSortIndexer:
    with Tapestry():
        src = Parameter("bp", str, default="in.bam", _config=KnotConfig(id="bp"))
        return BAMSortIndexer(bam_path=src, sort_by="coordinate", threads=4, _config=_CFG)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_invalid_sort_by(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "sort_by"):
            await knot.process(bam_path="in.bam", sort_by="position", threads=4)

    async def test_rejects_zero_threads(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "threads"):
            await knot.process(bam_path="in.bam", sort_by="coordinate", threads=0)

    async def test_coordinate_sort_returns_index_path(self) -> None:
        knot = _make_knot()
        out = await knot.process(bam_path="in.bam", sort_by="coordinate", threads=4)
        assert isinstance(out, dict)
        assert out["sort_by"] == "coordinate"
        assert out["index_path"] is not None

    async def test_name_sort_has_no_index(self) -> None:
        knot = _make_knot()
        out = await knot.process(bam_path="in.bam", sort_by="name", threads=4)
        assert out["index_path"] is None
