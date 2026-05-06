"""``PathwayEnricher`` — GSEA-style pathway enrichment.

Production version wraps GSEA / fgsea / enrichr; this stub returns an
empty enrichment mapping.

Algorithm:
    1. Receive ranked_genes sequence and gene_set_db string.
    2. Validate ranked_genes is a list/tuple of strings and gene_set_db is non-empty.
    3. Load gene set definitions from the named database.
    4. Compute enrichment scores via running-sum statistic over ranked list.
    5. Return mapping of pathway name to enrichment statistics.

Math:
    Enrichment score for gene set $S$ over ranked list $L$:

    $$ES(S) = \\max_{j} \\left| \\sum_{i=1}^{j} \\mathbf{1}[g_i \\in S] \\cdot w_i - \\sum_{i=1}^{j} \\mathbf{1}[g_i \\notin S] \\cdot \\frac{1}{N - |S|} \\right|$$

References:
    - Subramanian et al. (2005) Gene set enrichment analysis.
    - fgsea: https://bioconductor.org/packages/fgsea/
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
        ranked_genes: Knot | Sequence[str],
        gene_set_db: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            ranked_genes=ranked_genes,
            gene_set_db=gene_set_db,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        ranked_genes: Sequence[str],
        gene_set_db: str,
        **_: Any,
    ) -> Mapping[str, Mapping[str, float]]:
        """Run pathway enrichment on the ranked gene list against the gene-set database and return pathway-to-stats mapping.

        Args:
            ranked_genes: List or tuple of gene identifier strings in rank order.
            gene_set_db: Non-empty name of the gene-set database to query.

        Returns:
            Mapping of pathway name to enrichment statistics (empty at orchestration layer).

        Raises:
            TypeError: If ranked_genes is not list/tuple or contains non-strings.
            ValueError: If gene_set_db is empty.
        """
        if not isinstance(ranked_genes, (list, tuple)):
            raise TypeError("PathwayEnricher: ranked_genes must be list/tuple")
        for gene in ranked_genes:
            if not isinstance(gene, str):
                raise TypeError("PathwayEnricher: every gene must be a string")
        if not isinstance(gene_set_db, str) or not gene_set_db:
            raise ValueError("PathwayEnricher: gene_set_db must be a non-empty string")
        return {}
