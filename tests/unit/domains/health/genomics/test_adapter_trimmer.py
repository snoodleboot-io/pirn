"""Unit tests for :class:`AdapterTrimmer`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.health.genomics.adapter_trimmer import AdapterTrimmer
from pirn.tapestry import Tapestry

_CFG = KnotConfig(id="a")
_FASTQ = {"reads": [], "total_reads": 0}


def _make_knot() -> AdapterTrimmer:
    with Tapestry():
        src = Parameter("fq", dict, default=_FASTQ, _config=KnotConfig(id="fq"))
        return AdapterTrimmer(
            fastq=src,
            adapter_sequence="AGATCGGAA",
            min_length=20,
            quality_cutoff=20,
            _config=_CFG,
        )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_adapter(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "adapter_sequence"):
            await knot.process(fastq=_FASTQ, adapter_sequence="", min_length=20, quality_cutoff=20)

    async def test_rejects_zero_min_length(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "min_length"):
            await knot.process(fastq=_FASTQ, adapter_sequence="AGATCGGAA", min_length=0, quality_cutoff=20)

    async def test_rejects_quality_cutoff_too_high(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "quality_cutoff"):
            await knot.process(fastq=_FASTQ, adapter_sequence="AGATCGGAA", min_length=20, quality_cutoff=50)

    async def test_rejects_negative_quality_cutoff(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "quality_cutoff"):
            await knot.process(fastq=_FASTQ, adapter_sequence="AGATCGGAA", min_length=20, quality_cutoff=-1)

    async def test_returns_dict(self) -> None:
        knot = _make_knot()
        out = await knot.process(fastq=_FASTQ, adapter_sequence="AGATCGGAA", min_length=20, quality_cutoff=20)
        assert isinstance(out, dict)
        assert "n_trimmed" in out
        assert "trimmed_reads" in out
        assert "adapter_sequence" in out

    async def test_adapter_sequence_preserved(self) -> None:
        knot = _make_knot()
        out = await knot.process(fastq=_FASTQ, adapter_sequence="AGATCGGAA", min_length=20, quality_cutoff=20)
        assert out["adapter_sequence"] == "AGATCGGAA"
