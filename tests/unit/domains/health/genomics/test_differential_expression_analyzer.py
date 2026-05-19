"""Unit tests for :class:`DifferentialExpressionAnalyzer`."""

from __future__ import annotations

import unittest

try:
    import scipy  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("scipy not installed") from _e

from collections.abc import Mapping

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.genomics.differential_expression_analyzer import (
    DifferentialExpressionAnalyzer,
)

_CFG = KnotConfig(id="d")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> DifferentialExpressionAnalyzer:
        return DifferentialExpressionAnalyzer(
            case_counts={"S1": {"G1": 1.0}},
            control_counts={"S2": {"G1": 1.0}},
            gene_ids=["G1"],
            _config=_CFG,
        )

    async def test_rejects_non_mapping_case(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "case_counts"):
            await knot.process(case_counts=42, control_counts={}, gene_ids=[])  # type: ignore[arg-type]

    async def test_rejects_non_mapping_control(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "control_counts"):
            await knot.process(case_counts={}, control_counts=42, gene_ids=[])  # type: ignore[arg-type]

    async def test_rejects_non_sequence_genes(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "gene_ids"):
            await knot.process(case_counts={}, control_counts={}, gene_ids=42)  # type: ignore[arg-type]

    async def test_rejects_non_string_gene(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "string"):
            await knot.process(case_counts={}, control_counts={}, gene_ids=[1])  # type: ignore[list-item]

    async def test_returns_per_gene_mapping(self) -> None:
        knot = self._make_knot()
        out = await knot.process(
            case_counts={"S1": {"G1": 1.0}},
            control_counts={"S2": {"G1": 1.0}},
            gene_ids=["G1"],
        )
        assert isinstance(out, Mapping)
        assert "G1" in out
        assert "log2fc" in out["G1"]
