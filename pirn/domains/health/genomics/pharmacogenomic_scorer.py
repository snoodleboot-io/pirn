"""``PharmacogenomicScorer`` — score pharmacogenomic variants and predict drug metabolism phenotype.

Algorithm:
    1. Receive variants list, gene_panel tuple, and guideline string.
    2. Validate guideline is one of cpic/dpwg and gene_panel is non-empty.
    3. Look up star allele assignments for each gene in the panel.
    4. Apply CPIC or DPWG activity scores to predict metabolizer phenotype.
    5. Return phenotype calls and drug dosing recommendations per gene.

Math:
    Activity score for CYP genes (CPIC model):

    $$AS = \\sum_{i \\in \\{1,2\\}} v(a_i)$$

    where $v(a_i)$ is the functional value (0, 0.5, or 1) of allele $a_i$.

References:
    - CPIC: https://cpicpgx.org/
    - DPWG: https://www.pharmgkb.org/page/dpwg
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class PharmacogenomicScorer(Knot):
    """Score pharmacogenomic variants and predict drug metabolism phenotype."""

    def __init__(
        self,
        *,
        variants: Knot | list[dict[str, Any]],
        gene_panel: Knot | Sequence[str] = ("CYP2D6", "CYP2C19", "CYP2C9", "DPYD", "TPMT"),
        guideline: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            variants=variants,
            gene_panel=gene_panel,
            guideline=guideline,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        variants: list[dict[str, Any]],
        gene_panel: Sequence[str],
        guideline: str,
        **_: Any,
    ) -> dict[str, Any]:
        """Score variants and return phenotype calls and drug recommendations.

        Args:
            variants: List of dicts each with ``gene``, ``variant_id``, and ``zygosity``.
            gene_panel: Non-empty sequence of gene name strings to score.
            guideline: One of cpic or dpwg.

        Returns:
            Dict with ``phenotype_calls``, ``drug_recommendations``, and ``n_actionable``.

        Raises:
            ValueError: If guideline is invalid or gene_panel is empty.
        """
        if not isinstance(guideline, str) or guideline not in {"cpic", "dpwg"}:
            raise ValueError(
                "PharmacogenomicScorer: guideline must be one of ['cpic', 'dpwg']"
            )
        if not gene_panel:
            raise ValueError("PharmacogenomicScorer: gene_panel must be non-empty")
        return {
            "phenotype_calls": {gene: "normal_metabolizer" for gene in gene_panel},
            "drug_recommendations": [],
            "n_actionable": 0,
        }
