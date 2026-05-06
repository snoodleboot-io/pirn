"""Unit tests for :class:`PathwayEnricher`."""

from __future__ import annotations

from collections.abc import Mapping
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.genomics.pathway_enricher import PathwayEnricher

_CFG = KnotConfig(id="p")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> PathwayEnricher:
        return PathwayEnricher(ranked_genes=["G1"], gene_set_db="kegg", _config=_CFG)

    async def test_rejects_non_sequence(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "ranked_genes"):
            await knot.process(ranked_genes=42, gene_set_db="kegg")  # type: ignore[arg-type]

    async def test_rejects_non_string_gene(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "string"):
            await knot.process(ranked_genes=[1], gene_set_db="kegg")  # type: ignore[list-item]

    async def test_rejects_empty_db(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await knot.process(ranked_genes=[], gene_set_db="")

    async def test_returns_mapping(self) -> None:
        knot = self._make_knot()
        out = await knot.process(ranked_genes=["G1"], gene_set_db="kegg")
        assert isinstance(out, Mapping)
