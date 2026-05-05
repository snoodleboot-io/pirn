"""Unit tests for :class:`PharmacogenomicScorer`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.domains.health.genomics.pharmacogenomic_scorer import PharmacogenomicScorer
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_invalid_guideline(self) -> None:
        with self.assertRaisesRegex(ValueError, "guideline"):
            PharmacogenomicScorer(
                variants=Parameter("v", list, default=[], _config=KnotConfig(id="v")),
                guideline="fda",
                _config=KnotConfig(id="p"),
            )

    def test_rejects_empty_gene_panel(self) -> None:
        with self.assertRaisesRegex(ValueError, "gene_panel"):
            PharmacogenomicScorer(
                variants=Parameter("v", list, default=[], _config=KnotConfig(id="v")),
                gene_panel=(),
                guideline="cpic",
                _config=KnotConfig(id="p"),
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_dict(self) -> None:
        variants = [{"gene": "CYP2D6", "variant_id": "rs1065852", "zygosity": "het"}]
        with Tapestry() as t:
            PharmacogenomicScorer(
                variants=Parameter("v", list, default=variants, _config=KnotConfig(id="v")),
                guideline="cpic",
                _config=KnotConfig(id="p"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["p"]
        assert isinstance(out, dict)
        assert "phenotype_calls" in out
        assert "drug_recommendations" in out
        assert "n_actionable" in out

    async def test_phenotype_calls_keyed_by_gene(self) -> None:
        panel = ("CYP2D6", "TPMT")
        with Tapestry() as t:
            PharmacogenomicScorer(
                variants=Parameter("v", list, default=[], _config=KnotConfig(id="v")),
                gene_panel=panel,
                guideline="dpwg",
                _config=KnotConfig(id="p"),
            )
        result = await t.run(RunRequest())
        calls = result.outputs["p"]["phenotype_calls"]
        assert set(calls.keys()) == set(panel)
