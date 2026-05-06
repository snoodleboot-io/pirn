"""Unit tests for :class:`VCFFilter`."""

from __future__ import annotations
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.genomics.vcf_filter import VCFFilter

_CFG = KnotConfig(id="f")
_ROWS = (
    {"qual": 20.0, "af": 0.1},
    {"qual": 5.0, "af": 0.1},
    {"qual": 20.0, "af": 0.9},
)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> VCFFilter:
        return VCFFilter(rows=_ROWS, min_qual=10.0, max_af=0.5, _config=_CFG)

    async def test_rejects_non_sequence(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "rows"):
            await knot.process(rows=42, min_qual=10.0, max_af=0.5)  # type: ignore[arg-type]

    async def test_rejects_non_mapping_row(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "row"):
            await knot.process(rows=["x"], min_qual=10.0, max_af=0.5)  # type: ignore[list-item]

    async def test_rejects_non_numeric_min_qual(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "min_qual"):
            await knot.process(rows=[], min_qual="x", max_af=0.5)  # type: ignore[arg-type]

    async def test_rejects_out_of_range_af(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, r"\[0, 1\]"):
            await knot.process(rows=[], min_qual=10.0, max_af=1.5)

    async def test_filters_rows(self) -> None:
        knot = self._make_knot()
        out = await knot.process(rows=_ROWS, min_qual=10.0, max_af=0.5)
        assert isinstance(out, tuple)
        assert len(out) == 1
