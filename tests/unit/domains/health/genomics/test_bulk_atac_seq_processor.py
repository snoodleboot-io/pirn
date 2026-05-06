"""Unit tests for :class:`BulkATACSeqProcessor`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.health.genomics.bulk_atac_seq_processor import BulkATACSeqProcessor
from pirn.tapestry import Tapestry

_CFG = KnotConfig(id="b")
_BAM = {"aligned_reads": 1000000, "duplication_rate": 0.1, "bam_path": "in.bam"}


def _make_knot() -> BulkATACSeqProcessor:
    with Tapestry():
        src = Parameter("bam", dict, default=_BAM, _config=KnotConfig(id="bam"))
        return BulkATACSeqProcessor(bam=src, genome="hg38", _config=_CFG)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_genome(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "genome"):
            await knot.process(bam=_BAM, genome="")

    async def test_rejects_non_dict_bam(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(TypeError, "bam"):
            await knot.process(bam="not_a_dict", genome="hg38")  # type: ignore[arg-type]

    async def test_returns_dict(self) -> None:
        knot = _make_knot()
        out = await knot.process(bam=_BAM, genome="hg38")
        assert isinstance(out, dict)
        assert "peaks" in out
        assert "n_peaks" in out
        assert "tss_enrichment_score" in out
        assert "frip_score" in out
