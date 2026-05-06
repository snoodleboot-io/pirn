"""Unit tests for :class:`Bowtie2Aligner`."""

from __future__ import annotations
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.genomics.bowtie2_aligner import Bowtie2Aligner

_CFG = KnotConfig(id="a")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> Bowtie2Aligner:
        return Bowtie2Aligner(
            fastq_path="in.fastq",
            index_prefix="idx",
            output_bam_path="out.bam",
            _config=_CFG,
        )

    async def test_rejects_non_string_fastq(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "fastq_path"):
            await knot.process(fastq_path=42, index_prefix="idx", output_bam_path="out")  # type: ignore[arg-type]

    async def test_rejects_empty_fastq(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await knot.process(fastq_path="", index_prefix="idx", output_bam_path="out")

    async def test_returns_bam_path(self) -> None:
        knot = self._make_knot()
        out = await knot.process(fastq_path="in.fastq", index_prefix="idx", output_bam_path="out.bam")
        assert out == "out.bam"
