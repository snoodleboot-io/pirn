"""Unit tests for :class:`BAMSortIndexer`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.domains.health.genomics.bam_sort_indexer import BAMSortIndexer
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_invalid_sort_by(self) -> None:
        with self.assertRaisesRegex(ValueError, "sort_by"):
            BAMSortIndexer(
                bam_path=Parameter("bp", str, default="in.bam", _config=KnotConfig(id="bp")),
                sort_by="position",
                threads=4,
                _config=KnotConfig(id="b"),
            )

    def test_rejects_zero_threads(self) -> None:
        with self.assertRaisesRegex(ValueError, "threads"):
            BAMSortIndexer(
                bam_path=Parameter("bp", str, default="in.bam", _config=KnotConfig(id="bp")),
                sort_by="coordinate",
                threads=0,
                _config=KnotConfig(id="b"),
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_coordinate_sort_returns_index_path(self) -> None:
        with Tapestry() as t:
            BAMSortIndexer(
                bam_path=Parameter("bp", str, default="in.bam", _config=KnotConfig(id="bp")),
                sort_by="coordinate",
                threads=4,
                _config=KnotConfig(id="b"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["b"]
        assert isinstance(out, dict)
        assert out["sort_by"] == "coordinate"
        assert out["index_path"] is not None

    async def test_name_sort_has_no_index(self) -> None:
        with Tapestry() as t:
            BAMSortIndexer(
                bam_path=Parameter("bp", str, default="in.bam", _config=KnotConfig(id="bp")),
                sort_by="name",
                threads=4,
                _config=KnotConfig(id="b"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["b"]
        assert out["index_path"] is None
