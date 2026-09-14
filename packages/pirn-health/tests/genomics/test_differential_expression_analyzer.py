"""Unit tests for :class:`DifferentialExpressionAnalyzer`."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from collections.abc import Mapping
from unittest.mock import patch

import numpy as np
import pytest
from pirn.core.knot_config import KnotConfig

from pirn_health.genomics.differential_expression_analyzer import (
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

    @unittest.skipUnless(importlib.util.find_spec("scipy"), "scipy not installed")
    async def test_welch_pvalue_and_bh_adjustment(self) -> None:
        knot = self._make_knot()
        out = await knot.process(
            case_counts={"S1": {"G1": 10.0, "G2": 5.0}, "S2": {"G1": 12.0, "G2": 6.0}},
            control_counts={"S3": {"G1": 1.0, "G2": 5.5}, "S4": {"G1": 2.0, "G2": 5.0}},
            gene_ids=["G1", "G2"],
        )
        assert out["G1"]["log2fc"] == pytest.approx(np.log2(11.0 / 1.5))
        assert 0.0 < out["G1"]["pvalue"] < 0.05
        assert out["G2"]["pvalue"] > 0.05
        assert out["G1"]["padj"] >= out["G1"]["pvalue"]
        assert out["G1"]["padj"] <= out["G2"]["padj"] <= 1.0

    async def test_missing_scipy_raises_install_hint(self) -> None:
        knot = self._make_knot()
        with patch.dict(sys.modules, {"scipy.stats": None}):
            with self.assertRaisesRegex(ImportError, r"pirn-health\[health\]"):
                await knot.process(
                    case_counts={"S1": {"G1": 1.0}},
                    control_counts={"S2": {"G1": 1.0}},
                    gene_ids=["G1"],
                )
