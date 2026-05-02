"""``PathwayEnricher`` — GSEA-style pathway enrichment.

Production version wraps GSEA / fgsea / enrichr; this stub returns an
empty enrichment mapping.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class PathwayEnricher(Knot):
    """Run pathway enrichment over a ranked gene list."""

    def __init__(
        self,
        *,
        ranked_genes: Sequence[str],
        gene_set_db: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(ranked_genes, (list, tuple)):
            raise TypeError(
                "PathwayEnricher: ranked_genes must be list/tuple"
            )
        for gene in ranked_genes:
            if not isinstance(gene, str):
                raise TypeError(
                    "PathwayEnricher: every gene must be a string"
                )
        if not isinstance(gene_set_db, str) or not gene_set_db:
            raise ValueError(
                "PathwayEnricher: gene_set_db must be a non-empty string"
            )
        self._ranked_genes = tuple(ranked_genes)
        self._gene_set_db = gene_set_db
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> Mapping[str, Mapping[str, float]]:
        return {}
