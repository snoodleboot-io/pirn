"""Unit tests for :class:`GATKCaller`."""

from __future__ import annotations
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.genomics.gatk_caller import GATKCaller

_CFG = KnotConfig(id="g")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> GATKCaller:
        return GATKCaller(
            bam_path="in.bam",
            reference_path="ref.fa",
            output_vcf_path="out.vcf",
            _config=_CFG,
        )

    async def test_rejects_non_string(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "bam_path"):
            await knot.process(bam_path=42, reference_path="ref", output_vcf_path="out")  # type: ignore[arg-type]

    async def test_rejects_empty(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await knot.process(bam_path="", reference_path="ref", output_vcf_path="out")

    async def test_returns_vcf_path(self) -> None:
        knot = self._make_knot()
        out = await knot.process(bam_path="in.bam", reference_path="ref.fa", output_vcf_path="out.vcf")
        assert out == "out.vcf"
