"""Unit tests for :class:`SnpEffAnnotator`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.genomics.snpeff_annotator import SnpEffAnnotator
from pirn.tapestry import Tapestry


class TestConstruction:
    def test_rejects_non_string(self) -> None:
        with pytest.raises(TypeError, match="vcf_path"):
            SnpEffAnnotator(
                vcf_path=42,  # type: ignore[arg-type]
                genome_db="GRCh38",
                output_vcf_path="out",
                _config=KnotConfig(id="a"),
            )

    def test_rejects_empty(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            SnpEffAnnotator(
                vcf_path="",
                genome_db="GRCh38",
                output_vcf_path="out",
                _config=KnotConfig(id="a"),
            )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_annotated_path(self) -> None:
        with Tapestry() as t:
            SnpEffAnnotator(
                vcf_path="in.vcf",
                genome_db="GRCh38",
                output_vcf_path="out.vcf",
                _config=KnotConfig(id="a"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["a"]
        assert out == "out.vcf"
