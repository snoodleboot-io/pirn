"""Unit tests for :class:`BWAAligner`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.genomics.bwa_aligner import BWAAligner

_CFG = KnotConfig(id="a")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> BWAAligner:
        return BWAAligner(
            fastq_path="in.fastq",
            reference_path="ref.fa",
            output_bam_path="out.bam",
            _config=_CFG,
        )

    async def test_rejects_non_string(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "fastq_path"):
            await knot.process(fastq_path=42, reference_path="ref", output_bam_path="out")  # type: ignore[arg-type]

    async def test_rejects_empty(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await knot.process(fastq_path="", reference_path="ref", output_bam_path="out")

    async def test_returns_bam_path(self) -> None:
        knot = self._make_knot()
        out = await knot.process(fastq_path="in.fastq", reference_path="ref.fa", output_bam_path="out.bam")
        assert out == "out.bam"
