"""Unit tests for :class:`BulkATACSeqProcessor`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.domains.health.genomics.bulk_atac_seq_processor import BulkATACSeqProcessor
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_empty_genome(self) -> None:
        with self.assertRaisesRegex(ValueError, "genome"):
            BulkATACSeqProcessor(
                bam=Parameter("bam", dict, default={}, _config=KnotConfig(id="bam")),
                genome="",
                _config=KnotConfig(id="b"),
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_dict(self) -> None:
        bam_data = {"aligned_reads": 1000000, "duplication_rate": 0.1, "bam_path": "in.bam"}
        with Tapestry() as t:
            BulkATACSeqProcessor(
                bam=Parameter("bam", dict, default=bam_data, _config=KnotConfig(id="bam")),
                genome="hg38",
                _config=KnotConfig(id="b"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["b"]
        assert isinstance(out, dict)
        assert "peaks" in out
        assert "n_peaks" in out
        assert "tss_enrichment_score" in out
        assert "frip_score" in out
