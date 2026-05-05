"""Unit tests for :class:`VCFFilter`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.genomics.vcf_filter import VCFFilter
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_non_sequence(self) -> None:
        with self.assertRaisesRegex(TypeError, "rows"):
            VCFFilter(
                rows=42,  # type: ignore[arg-type]
                min_qual=10.0,
                max_af=0.5,
                _config=KnotConfig(id="f"),
            )

    def test_rejects_non_mapping_row(self) -> None:
        with self.assertRaisesRegex(TypeError, "row"):
            VCFFilter(
                rows=["x"],  # type: ignore[list-item]
                min_qual=10.0,
                max_af=0.5,
                _config=KnotConfig(id="f"),
            )

    def test_rejects_non_numeric_min_qual(self) -> None:
        with self.assertRaisesRegex(TypeError, "min_qual"):
            VCFFilter(
                rows=[],
                min_qual="x",  # type: ignore[arg-type]
                max_af=0.5,
                _config=KnotConfig(id="f"),
            )

    def test_rejects_out_of_range_af(self) -> None:
        with self.assertRaisesRegex(ValueError, r"\[0, 1\]"):
            VCFFilter(
                rows=[],
                min_qual=10.0,
                max_af=1.5,
                _config=KnotConfig(id="f"),
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_filters_rows(self) -> None:
        rows = (
            {"qual": 20.0, "af": 0.1},
            {"qual": 5.0, "af": 0.1},
            {"qual": 20.0, "af": 0.9},
        )
        with Tapestry() as t:
            VCFFilter(
                rows=rows,
                min_qual=10.0,
                max_af=0.5,
                _config=KnotConfig(id="f"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["f"]
        assert isinstance(out, tuple)
        assert len(out) == 1
