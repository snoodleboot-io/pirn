"""Unit tests for :class:`AdapterTrimmer`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.domains.health.genomics.adapter_trimmer import AdapterTrimmer
from pirn.tapestry import Tapestry


class TestConstruction:
    def test_rejects_empty_adapter(self) -> None:
        with pytest.raises(ValueError, match="adapter_sequence"):
            AdapterTrimmer(
                fastq=Parameter("fq", dict, default={}, _config=KnotConfig(id="fq")),
                adapter_sequence="",
                min_length=20,
                quality_cutoff=20,
                _config=KnotConfig(id="a"),
            )

    def test_rejects_zero_min_length(self) -> None:
        with pytest.raises(ValueError, match="min_length"):
            AdapterTrimmer(
                fastq=Parameter("fq", dict, default={}, _config=KnotConfig(id="fq")),
                adapter_sequence="AGATCGGAA",
                min_length=0,
                quality_cutoff=20,
                _config=KnotConfig(id="a"),
            )

    def test_rejects_quality_cutoff_too_high(self) -> None:
        with pytest.raises(ValueError, match="quality_cutoff"):
            AdapterTrimmer(
                fastq=Parameter("fq", dict, default={}, _config=KnotConfig(id="fq")),
                adapter_sequence="AGATCGGAA",
                min_length=20,
                quality_cutoff=50,
                _config=KnotConfig(id="a"),
            )

    def test_rejects_negative_quality_cutoff(self) -> None:
        with pytest.raises(ValueError, match="quality_cutoff"):
            AdapterTrimmer(
                fastq=Parameter("fq", dict, default={}, _config=KnotConfig(id="fq")),
                adapter_sequence="AGATCGGAA",
                min_length=20,
                quality_cutoff=-1,
                _config=KnotConfig(id="a"),
            )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_dict(self) -> None:
        fastq_data = {"reads": [], "total_reads": 0}
        with Tapestry() as t:
            AdapterTrimmer(
                fastq=Parameter("fq", dict, default=fastq_data, _config=KnotConfig(id="fq")),
                adapter_sequence="AGATCGGAA",
                min_length=20,
                quality_cutoff=20,
                _config=KnotConfig(id="a"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["a"]
        assert isinstance(out, dict)
        assert "n_trimmed" in out
        assert "trimmed_reads" in out
        assert "adapter_sequence" in out

    async def test_adapter_sequence_preserved(self) -> None:
        fastq_data = {"reads": [], "total_reads": 0}
        with Tapestry() as t:
            AdapterTrimmer(
                fastq=Parameter("fq", dict, default=fastq_data, _config=KnotConfig(id="fq")),
                adapter_sequence="AGATCGGAA",
                min_length=20,
                quality_cutoff=20,
                _config=KnotConfig(id="a"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["a"]["adapter_sequence"] == "AGATCGGAA"
