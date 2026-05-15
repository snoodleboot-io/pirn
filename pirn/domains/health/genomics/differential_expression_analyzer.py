"""``DifferentialExpressionAnalyzer`` — case/control DE analysis.

Production version wraps DESeq2 / edgeR / limma-voom (R) or PyDESeq2.
This stub returns an empty mapping ``gene_id -> {log2fc, pvalue, padj}``.

Algorithm:
    1. Receive case_counts, control_counts Mappings, and gene_ids sequence.
    2. Validate types.
    3. Normalize count matrices (TMM/RLE normalization).
    4. Fit a negative binomial GLM per gene.
    5. Compute Wald test statistics and adjust p-values (BH).

Math:
    $$\\log_2 FC_g = \\log_2\\!\\left(\\frac{\\mu_{g,\\text{case}}}{\\mu_{g,\\text{control}}}\\right)$$

References:
    - Love et al. (2014) Moderated estimation of fold change and dispersion (DESeq2).
    - PyDESeq2: https://pydeseq2.readthedocs.io/
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
from scipy import stats as ss

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


def _run_de(
    case_counts: dict[str, Mapping[str, float]],
    control_counts: dict[str, Mapping[str, float]],
    gene_ids: list[str],
) -> dict[str, dict[str, float]]:
    """Compute log2FC, Welch t-test p-value, and BH-adjusted p-value per gene."""
    log2fcs: list[float] = []
    pvalues: list[float] = []

    for gid in gene_ids:
        case_vals = np.array([s[gid] for s in case_counts.values() if gid in s], dtype=float)
        ctrl_vals = np.array([s[gid] for s in control_counts.values() if gid in s], dtype=float)

        mean_case = float(np.mean(case_vals)) if len(case_vals) > 0 else 0.0
        mean_ctrl = float(np.mean(ctrl_vals)) if len(ctrl_vals) > 0 else 0.0
        log2fc = np.log2(max(mean_case, 1e-10) / max(mean_ctrl, 1e-10))
        log2fcs.append(float(log2fc))

        if len(case_vals) < 2 or len(ctrl_vals) < 2:
            pvalues.append(1.0)
        else:
            result = ss.ttest_ind(case_vals, ctrl_vals, equal_var=False)
            pval = float(result.pvalue)
            if np.isnan(pval):
                pval = 1.0
            pvalues.append(pval)

    gene_count = len(gene_ids)
    if gene_count == 0:
        return {}

    # Benjamini-Hochberg correction
    order = np.argsort(pvalues)
    padjs = np.array(pvalues, dtype=float)
    for rank_minus1, sorted_index in enumerate(order):
        rank = rank_minus1 + 1
        padjs[sorted_index] = min(1.0, pvalues[sorted_index] * gene_count / rank)

    # Enforce monotonicity (scan from largest rank to smallest)
    for rank_minus1 in range(gene_count - 2, -1, -1):
        sorted_index = order[rank_minus1]
        next_sorted_index = order[rank_minus1 + 1]
        padjs[sorted_index] = min(padjs[sorted_index], padjs[next_sorted_index])

    return {
        gid: {"log2fc": log2fcs[i], "pvalue": pvalues[i], "padj": float(padjs[i])}
        for i, gid in enumerate(gene_ids)
    }


class DifferentialExpressionAnalyzer(Knot):
    """Run differential-expression analysis between case and control groups."""

    def __init__(
        self,
        *,
        case_counts: Knot | Mapping[str, Mapping[str, float]],
        control_counts: Knot | Mapping[str, Mapping[str, float]],
        gene_ids: Knot | Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            case_counts=case_counts,
            control_counts=control_counts,
            gene_ids=gene_ids,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        case_counts: Mapping[str, Mapping[str, float]],
        control_counts: Mapping[str, Mapping[str, float]],
        gene_ids: Sequence[str],
        **_: Any,
    ) -> Mapping[str, Mapping[str, float]]:
        """Compute log2 fold-change, p-value, and adjusted p-value for each gene and return the results mapping.

        Args:
            case_counts: Mapping of sample_id to gene-count mappings for case group.
            control_counts: Mapping of sample_id to gene-count mappings for control group.
            gene_ids: Sequence of gene identifier strings to analyze.

        Returns:
            A mapping from gene ID to a dict containing log2fc, pvalue, and padj statistics.

        Raises:
            TypeError: If case_counts or control_counts are not Mappings or gene_ids is not list/tuple of strings.
        """
        if not isinstance(case_counts, Mapping):
            raise TypeError("DifferentialExpressionAnalyzer: case_counts must be Mapping")
        if not isinstance(control_counts, Mapping):
            raise TypeError("DifferentialExpressionAnalyzer: control_counts must be Mapping")
        if not isinstance(gene_ids, (list, tuple)):
            raise TypeError("DifferentialExpressionAnalyzer: gene_ids must be list/tuple")
        for gid in gene_ids:
            if not isinstance(gid, str):
                raise TypeError("DifferentialExpressionAnalyzer: every gene id must be a string")
        return await asyncio.to_thread(
            _run_de, dict(case_counts), dict(control_counts), list(gene_ids)
        )
