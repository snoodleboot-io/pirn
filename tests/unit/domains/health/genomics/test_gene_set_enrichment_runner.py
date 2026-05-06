"""Unit tests for :class:`GeneSetEnrichmentRunner`."""

from __future__ import annotations
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.health.genomics.gene_set_enrichment_runner import GeneSetEnrichmentRunner
from pirn.tapestry import Tapestry

_CFG = KnotConfig(id="g")
_RANKS = [{"gene_id": "TP53", "rank_metric": 2.5}]


def _make_knot() -> GeneSetEnrichmentRunner:
    with Tapestry():
        src = Parameter("gr", list, default=_RANKS, _config=KnotConfig(id="gr"))
        return GeneSetEnrichmentRunner(
            gene_ranks=src,
            gene_set_database="hallmark",
            method="gsea",
            fdr_threshold=0.05,
            _config=_CFG,
        )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_invalid_database(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "gene_set_database"):
            await knot.process(gene_ranks=_RANKS, gene_set_database="invalid_db", method="gsea", fdr_threshold=0.05)

    async def test_rejects_invalid_method(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "method"):
            await knot.process(gene_ranks=_RANKS, gene_set_database="hallmark", method="hypergeometric", fdr_threshold=0.05)

    async def test_rejects_fdr_out_of_range(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "fdr_threshold"):
            await knot.process(gene_ranks=_RANKS, gene_set_database="hallmark", method="gsea", fdr_threshold=1.5)

    async def test_returns_dict(self) -> None:
        knot = _make_knot()
        out = await knot.process(gene_ranks=_RANKS, gene_set_database="hallmark", method="gsea", fdr_threshold=0.05)
        assert isinstance(out, dict)
        assert "enriched_sets" in out
        assert "n_significant" in out
        assert out["method"] == "gsea"
