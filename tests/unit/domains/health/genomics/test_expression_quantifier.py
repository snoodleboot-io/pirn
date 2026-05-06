"""Unit tests for :class:`ExpressionQuantifier`."""

from __future__ import annotations

import unittest
from collections.abc import Mapping

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.genomics.expression_quantifier import ExpressionQuantifier

_CFG = KnotConfig(id="q")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> ExpressionQuantifier:
        return ExpressionQuantifier(
            bam_path="in.bam",
            annotation_path="g.gtf",
            sample_id="S1",
            _config=_CFG,
        )

    async def test_rejects_empty_bam(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await knot.process(bam_path="", annotation_path="g.gtf", sample_id="S1")

    async def test_rejects_empty_annotation(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await knot.process(bam_path="in.bam", annotation_path="", sample_id="S1")

    async def test_rejects_empty_sample_id(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await knot.process(bam_path="in.bam", annotation_path="g.gtf", sample_id="")

    async def test_returns_mapping(self) -> None:
        knot = self._make_knot()
        out = await knot.process(bam_path="in.bam", annotation_path="g.gtf", sample_id="S1")
        assert isinstance(out, Mapping)
