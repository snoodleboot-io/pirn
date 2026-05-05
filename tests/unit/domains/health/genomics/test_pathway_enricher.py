"""Unit tests for :class:`PathwayEnricher`."""

from __future__ import annotations

from collections.abc import Mapping
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.genomics.pathway_enricher import PathwayEnricher
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_non_sequence(self) -> None:
        with self.assertRaisesRegex(TypeError, "ranked_genes"):
            PathwayEnricher(
                ranked_genes=42,  # type: ignore[arg-type]
                gene_set_db="kegg",
                _config=KnotConfig(id="p"),
            )

    def test_rejects_non_string_gene(self) -> None:
        with self.assertRaisesRegex(TypeError, "string"):
            PathwayEnricher(
                ranked_genes=[1],  # type: ignore[list-item]
                gene_set_db="kegg",
                _config=KnotConfig(id="p"),
            )

    def test_rejects_empty_db(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-empty"):
            PathwayEnricher(
                ranked_genes=[],
                gene_set_db="",
                _config=KnotConfig(id="p"),
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_mapping(self) -> None:
        with Tapestry() as t:
            PathwayEnricher(
                ranked_genes=["G1"],
                gene_set_db="kegg",
                _config=KnotConfig(id="p"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["p"]
        assert isinstance(out, Mapping)
