"""``DifferentialExpressionAnalyzer`` — case/control DE analysis.

Production version wraps DESeq2 / edgeR / limma-voom (R) or PyDESeq2.
This stub returns an empty mapping ``gene_id -> {log2fc, pvalue, padj}``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class DifferentialExpressionAnalyzer(Knot):
    """Run differential-expression analysis between case and control groups."""

    def __init__(
        self,
        *,
        case_counts: Mapping[str, Mapping[str, float]],
        control_counts: Mapping[str, Mapping[str, float]],
        gene_ids: Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(case_counts, Mapping):
            raise TypeError(
                "DifferentialExpressionAnalyzer: case_counts must be Mapping"
            )
        if not isinstance(control_counts, Mapping):
            raise TypeError(
                "DifferentialExpressionAnalyzer: control_counts must be Mapping"
            )
        if not isinstance(gene_ids, (list, tuple)):
            raise TypeError(
                "DifferentialExpressionAnalyzer: gene_ids must be list/tuple"
            )
        for gid in gene_ids:
            if not isinstance(gid, str):
                raise TypeError(
                    "DifferentialExpressionAnalyzer: every gene id must be a string"
                )
        self._case_counts = dict(case_counts)
        self._control_counts = dict(control_counts)
        self._gene_ids = tuple(gene_ids)
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> Mapping[str, Mapping[str, float]]:
        """Compute log2 fold-change, p-value, and adjusted p-value for each gene and return the results mapping.

        Returns:
            A mapping from gene ID to a dict containing log2fc, pvalue, and padj statistics.
        """
        return {gid: {"log2fc": 0.0, "pvalue": 1.0, "padj": 1.0} for gid in self._gene_ids}
