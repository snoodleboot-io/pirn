"""Unit tests for :class:`VCFMerger`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.genomics.vcf_merger import VCFMerger
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_non_sequence(self) -> None:
        with self.assertRaisesRegex(TypeError, "vcf_paths"):
            VCFMerger(
                vcf_paths=42,  # type: ignore[arg-type]
                output_vcf_path="out",
                _config=KnotConfig(id="m"),
            )

    def test_rejects_empty_sequence(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-empty"):
            VCFMerger(
                vcf_paths=[],
                output_vcf_path="out",
                _config=KnotConfig(id="m"),
            )

    def test_rejects_empty_path(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-empty"):
            VCFMerger(
                vcf_paths=[""],
                output_vcf_path="out",
                _config=KnotConfig(id="m"),
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_merged_path(self) -> None:
        with Tapestry() as t:
            VCFMerger(
                vcf_paths=["a.vcf", "b.vcf"],
                output_vcf_path="merged.vcf",
                _config=KnotConfig(id="m"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["m"]
        assert out == "merged.vcf"
