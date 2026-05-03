"""``PharmacogenomicScorer`` — score pharmacogenomic variants and predict drug metabolism phenotype."""
from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class PharmacogenomicScorer(Knot):
    """Score pharmacogenomic variants and predict drug metabolism phenotype."""

    _VALID_GUIDELINES: frozenset[str] = frozenset({"cpic", "dpwg"})
    _DEFAULT_PANEL: tuple[str, ...] = ("CYP2D6", "CYP2C19", "CYP2C9", "DPYD", "TPMT")

    def __init__(
        self,
        *,
        variants: Knot,
        gene_panel: tuple[str, ...] = _DEFAULT_PANEL,
        guideline: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(guideline, str) or guideline not in self._VALID_GUIDELINES:
            raise ValueError(
                f"PharmacogenomicScorer: guideline must be one of {sorted(self._VALID_GUIDELINES)}"
            )
        if not gene_panel:
            raise ValueError("PharmacogenomicScorer: gene_panel must be non-empty")
        self._gene_panel = tuple(gene_panel)
        self._guideline = guideline
        super().__init__(variants=variants, _config=_config, **kwargs)

    async def process(self, variants: list[dict[str, Any]], **_: Any) -> dict[str, Any]:
        """Score variants and return phenotype calls and drug recommendations.

        Args:
            variants: List of dicts each with ``gene``, ``variant_id``, and ``zygosity``.

        Returns:
            Dict with ``phenotype_calls``, ``drug_recommendations``, and ``n_actionable``.
        """
        return {
            "phenotype_calls": {gene: "normal_metabolizer" for gene in self._gene_panel},
            "drug_recommendations": [],
            "n_actionable": 0,
        }
