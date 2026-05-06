"""Unit tests for :class:`FastqQualityController`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.genomics.fastq_quality_controller import FastqQualityController
from pirn.domains.health.types.genomics_record import GenomicsRecord

_CFG = KnotConfig(id="q")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> FastqQualityController:
        return FastqQualityController(fastq_path="x.fq", sample_id="S1", _config=_CFG)

    async def test_rejects_non_string_path(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "fastq_path"):
            await knot.process(fastq_path=42, sample_id="S1")  # type: ignore[arg-type]

    async def test_rejects_empty_path(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await knot.process(fastq_path="", sample_id="S1")

    async def test_rejects_empty_sample(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await knot.process(fastq_path="x.fq", sample_id="")

    async def test_returns_genomics_record(self) -> None:
        knot = self._make_knot()
        out = await knot.process(fastq_path="x.fq", sample_id="S1")
        assert isinstance(out, GenomicsRecord)
        assert out.sample_id == "S1"
