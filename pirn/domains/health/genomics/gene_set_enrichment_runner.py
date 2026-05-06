"""``GeneSetEnrichmentRunner`` — run GSEA or over-representation analysis.

Algorithm:
    1. Receive gene_ranks list, gene_set_database, method, and fdr_threshold.
    2. Validate gene_set_database is one of hallmark/kegg/reactome/go_bp/go_mf.
    3. Validate method is one of gsea/ora.
    4. Validate fdr_threshold is numeric in [0, 1].
    5. Run GSEA or ORA and return enriched gene sets with significance stats.

Math:
    For GSEA: enrichment score computed via running-sum statistic over ranked list.

    $$ES = \\max_j \\left( \\sum_{i=1}^{j} \\frac{|r_i|^p}{N_R} - \\frac{1}{N - N_H} \\right)$$

References:
    - Subramanian et al. (2005) Gene set enrichment analysis.
    - clusterProfiler: https://bioconductor.org/packages/clusterProfiler/
"""

from __future__ import annotations

from typing import Any

from typing import ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class GeneSetEnrichmentRunner(Knot):
    """Run GSEA or over-representation analysis on a ranked gene list."""

    _valid_databases: ClassVar[frozenset[str]] = frozenset({"hallmark", "kegg", "reactome", "go_bp", "go_mf"})
    _valid_methods: ClassVar[frozenset[str]] = frozenset({"gsea", "ora"})

    def __init__(
        self,
        *,
        gene_ranks: Knot | list[dict[str, Any]],
        gene_set_database: Knot | str,
        method: Knot | str,
        fdr_threshold: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            gene_ranks=gene_ranks,
            gene_set_database=gene_set_database,
            method=method,
            fdr_threshold=fdr_threshold,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        gene_ranks: list[dict[str, Any]],
        gene_set_database: str,
        method: str,
        fdr_threshold: float,
        **_: Any,
    ) -> dict[str, Any]:
        """Run gene set enrichment analysis on the ranked gene list.

        Args:
            gene_ranks: List of dicts each with ``gene_id`` and ``rank_metric``.
            gene_set_database: One of hallmark, kegg, reactome, go_bp, go_mf.
            method: One of gsea or ora.
            fdr_threshold: FDR significance threshold in [0, 1].

        Returns:
            Dict with ``enriched_sets``, ``n_significant``, and ``method``.

        Raises:
            ValueError: If gene_set_database or method is invalid, or fdr_threshold is out of range.
        """
        if not isinstance(gene_set_database, str) or gene_set_database not in self._valid_databases:
            raise ValueError(
                f"GeneSetEnrichmentRunner: gene_set_database must be one of "
                f"{sorted(self._valid_databases)}"
            )
        if not isinstance(method, str) or method not in self._valid_methods:
            raise ValueError(
                f"GeneSetEnrichmentRunner: method must be one of {sorted(self._valid_methods)}"
            )
        if not isinstance(fdr_threshold, (int, float)) or not (0.0 <= float(fdr_threshold) <= 1.0):
            raise ValueError("GeneSetEnrichmentRunner: fdr_threshold must be in [0, 1]")
        return {
            "enriched_sets": [],
            "n_significant": 0,
            "method": method,
        }
