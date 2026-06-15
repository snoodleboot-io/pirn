"""Unit tests for :class:`VCFFilter`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn_health.genomics.vcf_filter import VCFFilter

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

    async def test_raises_on_missing_qual_field(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(KeyError, "qual"):
            await knot.process(rows=[{"af": 0.1}], min_qual=10.0, max_af=0.5)

    async def test_raises_on_missing_af_field(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(KeyError, "af"):
            await knot.process(rows=[{"qual": 20.0}], min_qual=10.0, max_af=0.5)

    async def test_custom_field_names(self) -> None:
        knot = self._make_knot()
        rows = [{"QUAL": 20.0, "INFO_AF": 0.1}, {"QUAL": 5.0, "INFO_AF": 0.1}]
        out = await knot.process(
            rows=rows, min_qual=10.0, max_af=0.5,
            qual_field="QUAL", af_field="INFO_AF",
        )
        assert len(out) == 1
        assert out[0]["QUAL"] == 20.0

    async def test_missing_af_does_not_silently_pass(self) -> None:
        """Previously, missing af defaulted to 0.0 which always passed af <= max_af."""
        knot = self._make_knot()
        with self.assertRaises(KeyError):
            await knot.process(rows=[{"qual": 50.0}], min_qual=10.0, max_af=0.5)
