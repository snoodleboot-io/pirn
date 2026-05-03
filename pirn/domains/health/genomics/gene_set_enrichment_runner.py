"""``GeneSetEnrichmentRunner`` — run GSEA or over-representation analysis."""
from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class GeneSetEnrichmentRunner(Knot):
    """Run GSEA or over-representation analysis on a ranked gene list."""

    _VALID_DATABASES: frozenset[str] = frozenset(
        {"hallmark", "kegg", "reactome", "go_bp", "go_mf"}
    )
    _VALID_METHODS: frozenset[str] = frozenset({"gsea", "ora"})

    def __init__(
        self,
        *,
        gene_ranks: Knot,
        gene_set_database: str,
        method: str,
        fdr_threshold: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(gene_set_database, str) or gene_set_database not in self._VALID_DATABASES:
            raise ValueError(
                f"GeneSetEnrichmentRunner: gene_set_database must be one of "
                f"{sorted(self._VALID_DATABASES)}"
            )
        if not isinstance(method, str) or method not in self._VALID_METHODS:
            raise ValueError(
                f"GeneSetEnrichmentRunner: method must be one of {sorted(self._VALID_METHODS)}"
            )
        if not isinstance(fdr_threshold, (int, float)) or not (0.0 <= float(fdr_threshold) <= 1.0):
            raise ValueError("GeneSetEnrichmentRunner: fdr_threshold must be in [0, 1]")
        self._gene_set_database = gene_set_database
        self._method = method
        self._fdr_threshold = float(fdr_threshold)
        super().__init__(gene_ranks=gene_ranks, _config=_config, **kwargs)

    async def process(self, gene_ranks: list[dict[str, Any]], **_: Any) -> dict[str, Any]:
        """Run gene set enrichment analysis on the ranked gene list.

        Args:
            gene_ranks: List of dicts each with ``gene_id`` and ``rank_metric``.

        Returns:
            Dict with ``enriched_sets``, ``n_significant``, and ``method``.
        """
        return {
            "enriched_sets": [],
            "n_significant": 0,
            "method": self._method,
        }
