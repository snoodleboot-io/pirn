"""Unit tests for :class:`GeneSetEnrichmentRunner`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.domains.health.genomics.gene_set_enrichment_runner import GeneSetEnrichmentRunner
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_invalid_database(self) -> None:
        with self.assertRaisesRegex(ValueError, "gene_set_database"):
            GeneSetEnrichmentRunner(
                gene_ranks=Parameter("gr", list, default=[], _config=KnotConfig(id="gr")),
                gene_set_database="invalid_db",
                method="gsea",
                fdr_threshold=0.05,
                _config=KnotConfig(id="g"),
            )

    def test_rejects_invalid_method(self) -> None:
        with self.assertRaisesRegex(ValueError, "method"):
            GeneSetEnrichmentRunner(
                gene_ranks=Parameter("gr", list, default=[], _config=KnotConfig(id="gr")),
                gene_set_database="hallmark",
                method="hypergeometric",
                fdr_threshold=0.05,
                _config=KnotConfig(id="g"),
            )

    def test_rejects_fdr_out_of_range(self) -> None:
        with self.assertRaisesRegex(ValueError, "fdr_threshold"):
            GeneSetEnrichmentRunner(
                gene_ranks=Parameter("gr", list, default=[], _config=KnotConfig(id="gr")),
                gene_set_database="hallmark",
                method="gsea",
                fdr_threshold=1.5,
                _config=KnotConfig(id="g"),
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_dict(self) -> None:
        ranks = [{"gene_id": "TP53", "rank_metric": 2.5}]
        with Tapestry() as t:
            GeneSetEnrichmentRunner(
                gene_ranks=Parameter("gr", list, default=ranks, _config=KnotConfig(id="gr")),
                gene_set_database="hallmark",
                method="gsea",
                fdr_threshold=0.05,
                _config=KnotConfig(id="g"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["g"]
        assert isinstance(out, dict)
        assert "enriched_sets" in out
        assert "n_significant" in out
        assert out["method"] == "gsea"
