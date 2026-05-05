"""Unit tests for :class:`GATKCaller`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.genomics.gatk_caller import GATKCaller
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_non_string(self) -> None:
        with self.assertRaisesRegex(TypeError, "bam_path"):
            GATKCaller(
                bam_path=42,  # type: ignore[arg-type]
                reference_path="ref",
                output_vcf_path="out",
                _config=KnotConfig(id="g"),
            )

    def test_rejects_empty(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-empty"):
            GATKCaller(
                bam_path="",
                reference_path="ref",
                output_vcf_path="out",
                _config=KnotConfig(id="g"),
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_vcf_path(self) -> None:
        with Tapestry() as t:
            GATKCaller(
                bam_path="in.bam",
                reference_path="ref.fa",
                output_vcf_path="out.vcf",
                _config=KnotConfig(id="g"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["g"]
        assert out == "out.vcf"
