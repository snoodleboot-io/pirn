"""Unit tests for :class:`Bowtie2Aligner`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.genomics.bowtie2_aligner import Bowtie2Aligner
from pirn.tapestry import Tapestry


class TestConstruction:
    def test_rejects_non_string_fastq(self) -> None:
        with pytest.raises(TypeError, match="fastq_path"):
            Bowtie2Aligner(
                fastq_path=42,  # type: ignore[arg-type]
                index_prefix="idx",
                output_bam_path="out",
                _config=KnotConfig(id="a"),
            )

    def test_rejects_empty_fastq(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            Bowtie2Aligner(
                fastq_path="",
                index_prefix="idx",
                output_bam_path="out",
                _config=KnotConfig(id="a"),
            )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_bam_path(self) -> None:
        with Tapestry() as t:
            Bowtie2Aligner(
                fastq_path="in.fastq",
                index_prefix="idx",
                output_bam_path="out.bam",
                _config=KnotConfig(id="a"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["a"]
        assert out == "out.bam"
