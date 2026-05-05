"""Unit tests for :class:`DifferentialExpressionAnalyzer`."""

from __future__ import annotations

from collections.abc import Mapping
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.genomics.differential_expression_analyzer import (
    DifferentialExpressionAnalyzer,
)
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_non_mapping_case(self) -> None:
        with self.assertRaisesRegex(TypeError, "case_counts"):
            DifferentialExpressionAnalyzer(
                case_counts=42,  # type: ignore[arg-type]
                control_counts={},
                gene_ids=[],
                _config=KnotConfig(id="d"),
            )

    def test_rejects_non_mapping_control(self) -> None:
        with self.assertRaisesRegex(TypeError, "control_counts"):
            DifferentialExpressionAnalyzer(
                case_counts={},
                control_counts=42,  # type: ignore[arg-type]
                gene_ids=[],
                _config=KnotConfig(id="d"),
            )

    def test_rejects_non_sequence_genes(self) -> None:
        with self.assertRaisesRegex(TypeError, "gene_ids"):
            DifferentialExpressionAnalyzer(
                case_counts={},
                control_counts={},
                gene_ids=42,  # type: ignore[arg-type]
                _config=KnotConfig(id="d"),
            )

    def test_rejects_non_string_gene(self) -> None:
        with self.assertRaisesRegex(TypeError, "string"):
            DifferentialExpressionAnalyzer(
                case_counts={},
                control_counts={},
                gene_ids=[1],  # type: ignore[list-item]
                _config=KnotConfig(id="d"),
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_per_gene_mapping(self) -> None:
        with Tapestry() as t:
            DifferentialExpressionAnalyzer(
                case_counts={"S1": {"G1": 1.0}},
                control_counts={"S2": {"G1": 1.0}},
                gene_ids=["G1"],
                _config=KnotConfig(id="d"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["d"]
        assert isinstance(out, Mapping)
        assert "G1" in out
        assert "log2fc" in out["G1"]
