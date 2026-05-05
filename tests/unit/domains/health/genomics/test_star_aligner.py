"""Unit tests for :class:`STARAligner`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.genomics.star_aligner import STARAligner
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_non_string(self) -> None:
        with self.assertRaisesRegex(TypeError, "fastq_path"):
            STARAligner(
                fastq_path=42,  # type: ignore[arg-type]
                genome_dir="g",
                output_bam_path="out",
                _config=KnotConfig(id="a"),
            )

    def test_rejects_empty(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-empty"):
            STARAligner(
                fastq_path="",
                genome_dir="g",
                output_bam_path="out",
                _config=KnotConfig(id="a"),
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_bam_path(self) -> None:
        with Tapestry() as t:
            STARAligner(
                fastq_path="in.fastq",
                genome_dir="g",
                output_bam_path="out.bam",
                _config=KnotConfig(id="a"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["a"]
        assert out == "out.bam"
