"""Unit tests for :class:`VCFMerger`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.genomics.vcf_merger import VCFMerger

_CFG = KnotConfig(id="m")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> VCFMerger:
        return VCFMerger(
            vcf_paths=["a.vcf", "b.vcf"],
            output_vcf_path="merged.vcf",
            _config=_CFG,
        )

    async def test_rejects_non_sequence(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "vcf_paths"):
            await knot.process(vcf_paths=42, output_vcf_path="out")  # type: ignore[arg-type]

    async def test_rejects_empty_sequence(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await knot.process(vcf_paths=[], output_vcf_path="out")

    async def test_rejects_empty_path(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await knot.process(vcf_paths=[""], output_vcf_path="out")

    async def test_returns_merged_path(self) -> None:
        knot = self._make_knot()
        out = await knot.process(vcf_paths=["a.vcf", "b.vcf"], output_vcf_path="merged.vcf")
        assert out == "merged.vcf"
