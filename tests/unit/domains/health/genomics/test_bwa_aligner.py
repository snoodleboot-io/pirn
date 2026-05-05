"""Unit tests for :class:`BWAAligner`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.genomics.bwa_aligner import BWAAligner
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_non_string(self) -> None:
        with self.assertRaisesRegex(TypeError, "fastq_path"):
            BWAAligner(
                fastq_path=42,  # type: ignore[arg-type]
                reference_path="ref",
                output_bam_path="out",
                _config=KnotConfig(id="a"),
            )

    def test_rejects_empty(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-empty"):
            BWAAligner(
                fastq_path="",
                reference_path="ref",
                output_bam_path="out",
                _config=KnotConfig(id="a"),
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_bam_path(self) -> None:
        with Tapestry() as t:
            BWAAligner(
                fastq_path="in.fastq",
                reference_path="ref.fa",
                output_bam_path="out.bam",
                _config=KnotConfig(id="a"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["a"]
        assert out == "out.bam"
