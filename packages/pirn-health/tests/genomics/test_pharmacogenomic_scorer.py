"""Unit tests for :class:`PharmacogenomicScorer`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.tapestry import Tapestry
from pirn_health.genomics.pharmacogenomic_scorer import PharmacogenomicScorer

_CFG = KnotConfig(id="p")
_VARIANTS = [{"gene": "CYP2D6", "variant_id": "rs1065852", "zygosity": "het"}]


def _make_knot() -> PharmacogenomicScorer:
    with Tapestry():
        src = Parameter("v", list, default=_VARIANTS, _config=KnotConfig(id="v"))
        return PharmacogenomicScorer(variants=src, guideline="cpic", _config=_CFG)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_invalid_guideline(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "guideline"):
            await knot.process(variants=_VARIANTS, gene_panel=("CYP2D6",), guideline="fda")

    async def test_rejects_empty_gene_panel(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "gene_panel"):
            await knot.process(variants=_VARIANTS, gene_panel=(), guideline="cpic")

    async def test_returns_dict(self) -> None:
        knot = _make_knot()
        out = await knot.process(variants=_VARIANTS, gene_panel=("CYP2D6",), guideline="cpic")
        assert isinstance(out, dict)
        assert "phenotype_calls" in out
        assert "drug_recommendations" in out
        assert "n_actionable" in out

    async def test_phenotype_calls_keyed_by_gene(self) -> None:
        knot = _make_knot()
        panel = ("CYP2D6", "TPMT")
        out = await knot.process(variants=[], gene_panel=panel, guideline="dpwg")
        assert set(out["phenotype_calls"].keys()) == set(panel)
