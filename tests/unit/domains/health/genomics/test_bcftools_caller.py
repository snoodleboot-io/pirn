"""Unit tests for :class:`BCFtoolsCaller`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.genomics.bcftools_caller import BCFtoolsCaller
from pirn.tapestry import Tapestry


class TestConstruction:
    def test_rejects_non_string_bam(self) -> None:
        with pytest.raises(TypeError, match="bam_path"):
            BCFtoolsCaller(
                bam_path=42,  # type: ignore[arg-type]
                reference_path="ref",
                output_vcf_path="out",
                _config=KnotConfig(id="b"),
            )

    def test_rejects_empty_bam(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            BCFtoolsCaller(
                bam_path="",
                reference_path="ref",
                output_vcf_path="out",
                _config=KnotConfig(id="b"),
            )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_vcf_path(self) -> None:
        with Tapestry() as t:
            BCFtoolsCaller(
                bam_path="in.bam",
                reference_path="ref.fa",
                output_vcf_path="out.vcf",
                _config=KnotConfig(id="b"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["b"]
        assert out == "out.vcf"
