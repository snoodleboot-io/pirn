"""Unit tests for :class:`GenomicsQCCheck`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn_health.genomics.genomics_qc_error import GenomicsQCError
from pirn_health.genomics.genomics_qc_gate import GenomicsQCCheck, GenomicsQCGate
from pirn_health.types.genomics_record import GenomicsRecord

_CFG = KnotConfig(id="g")
_RECORD_OK = GenomicsRecord(sample_id="S1", locus="", genotype="", quality_score=20.0)
_RECORD_LOW = GenomicsRecord(sample_id="S1", locus="", genotype="", quality_score=5.0)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> GenomicsQCCheck:
        return GenomicsQCCheck(records=(_RECORD_OK,), min_quality=10.0, _config=_CFG)

    async def test_rejects_non_sequence(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "records"):
            await knot.process(records=42, min_quality=10.0)  # type: ignore[arg-type]

    async def test_rejects_non_record(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "GenomicsRecord"):
            await knot.process(records=["x"], min_quality=10.0)  # type: ignore[list-item]

    async def test_rejects_non_numeric_threshold(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "numeric"):
            await knot.process(records=(), min_quality="x")  # type: ignore[arg-type]

    async def test_passes_when_quality_above(self) -> None:
        knot = self._make_knot()
        out = await knot.process(records=(_RECORD_OK,), min_quality=10.0)
        assert isinstance(out, tuple)
        assert len(out) == 1

    async def test_raises_when_quality_below(self) -> None:
        knot = self._make_knot()
        with self.assertRaises(GenomicsQCError):
            await knot.process(records=(_RECORD_LOW,), min_quality=10.0)

    def test_alias_points_to_check(self) -> None:
        assert GenomicsQCGate is GenomicsQCCheck
