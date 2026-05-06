"""Unit tests for :class:`CNVDetector`."""

from __future__ import annotations
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.genomics.cnv_detector import CNVDetector

_CFG = KnotConfig(id="d")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> CNVDetector:
        return CNVDetector(
            bam_path="in.bam",
            reference_path="ref.fa",
            sample_id="S1",
            _config=_CFG,
        )

    async def test_rejects_empty_bam(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await knot.process(bam_path="", reference_path="ref", sample_id="S1")

    async def test_rejects_empty_sample(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await knot.process(bam_path="in.bam", reference_path="ref", sample_id="")

    async def test_returns_tuple(self) -> None:
        knot = self._make_knot()
        out = await knot.process(bam_path="in.bam", reference_path="ref.fa", sample_id="S1")
        assert isinstance(out, tuple)
