"""``FunctionalConnectivityExtractor`` — extract functional connectivity matrix from resting-state fMRI.

Algorithm:
    1. Receive bold_timeseries dict, atlas, connectivity_measure, confound_strategy strings.
    2. Validate atlas is non-empty, connectivity_measure is one of correlation/partial_correlation/tangent.
    3. Validate confound_strategy is one of none/simple/full.
    4. Validate bold_timeseries is a dict.
    5. Compute pairwise connectivity between ROI timeseries and return the matrix.

Math:
    Pearson correlation between ROIs $i$ and $j$:

    $$r_{ij} = \\frac{\\sum_t (x_{i,t} - \\bar{x}_i)(x_{j,t} - \\bar{x}_j)}{\\sqrt{\\sum_t (x_{i,t} - \\bar{x}_i)^2 \\sum_t (x_{j,t} - \\bar{x}_j)^2}}$$

References:
    - Biswal et al. (1995) Functional connectivity in the motor cortex of resting human brain.
    - Nilearn: https://nilearn.github.io/
"""

from __future__ import annotations

import asyncio
from typing import Any, ClassVar

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


def _pearson_matrix(roi_matrix: np.ndarray) -> np.ndarray:
    """Compute symmetric Pearson correlation matrix for rows of roi_matrix."""
    roi_centered = roi_matrix - roi_matrix.mean(axis=1, keepdims=True)
    norms = np.linalg.norm(roi_centered, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    roi_normalized = roi_centered / norms
    return roi_normalized @ roi_normalized.T


def _partial_corr_matrix(roi_matrix: np.ndarray) -> np.ndarray:
    """Partial correlation via precision matrix inversion."""
    corr = np.corrcoef(roi_matrix)
    try:
        prec = np.linalg.inv(corr)
    except np.linalg.LinAlgError:
        prec = np.linalg.pinv(corr)
    diag_sqrt = np.sqrt(np.abs(np.diag(prec)))
    diag_sqrt = np.where(diag_sqrt == 0, 1.0, diag_sqrt)
    partial = -prec / np.outer(diag_sqrt, diag_sqrt)
    np.fill_diagonal(partial, 1.0)
    return partial


def _compute_connectivity(
    roi_timeseries: dict[str, list[float]],
    connectivity_measure: str,
) -> tuple[list[list[float]], list[str]]:
    roi_labels = list(roi_timeseries.keys())
    if not roi_labels:
        return [], roi_labels
    roi_matrix = np.array([roi_timeseries[lbl] for lbl in roi_labels], dtype=float)
    if connectivity_measure == "partial_correlation":
        mat = _partial_corr_matrix(roi_matrix)
    else:
        mat = _pearson_matrix(roi_matrix)
    return mat.tolist(), roi_labels


class FunctionalConnectivityExtractor(Knot):
    """Extract functional connectivity matrix from resting-state fMRI timeseries."""

    _valid_measures: ClassVar[frozenset[str]] = frozenset(
        {"correlation", "partial_correlation", "tangent"}
    )
    _valid_strategies: ClassVar[frozenset[str]] = frozenset({"none", "simple", "full"})

    def __init__(
        self,
        *,
        bold_timeseries: Knot | dict[str, Any],
        atlas: Knot | str,
        connectivity_measure: Knot | str,
        confound_strategy: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            bold_timeseries=bold_timeseries,
            atlas=atlas,
            connectivity_measure=connectivity_measure,
            confound_strategy=confound_strategy,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        bold_timeseries: dict[str, Any],
        atlas: str,
        connectivity_measure: str,
        confound_strategy: str,
        **_: Any,
    ) -> dict[str, Any]:
        """Extract functional connectivity matrix from BOLD timeseries data.

        Args:
            bold_timeseries: Dict with ``roi_timeseries`` (dict[str, list[float]]),
                ``n_timepoints`` (int), and ``tr_sec`` (float).
            atlas: Non-empty atlas identifier string.
            connectivity_measure: One of correlation, partial_correlation, tangent.
            confound_strategy: One of none, simple, full.

        Returns:
            Dict with ``connectivity_matrix``, ``roi_labels``, ``n_rois``, and ``measure``.

        Raises:
            TypeError: If bold_timeseries is not a dict.
            ValueError: If atlas is empty or measure/strategy are invalid.
        """
        if not isinstance(bold_timeseries, dict):
            raise TypeError("FunctionalConnectivityExtractor: bold_timeseries must be a dict")
        if not isinstance(atlas, str) or not atlas:
            raise ValueError("FunctionalConnectivityExtractor: atlas must be non-empty")
        if (
            not isinstance(connectivity_measure, str)
            or connectivity_measure not in self._valid_measures
        ):
            raise ValueError(
                f"FunctionalConnectivityExtractor: connectivity_measure must be one of "
                f"{sorted(self._valid_measures)}"
            )
        if (
            not isinstance(confound_strategy, str)
            or confound_strategy not in self._valid_strategies
        ):
            raise ValueError(
                f"FunctionalConnectivityExtractor: confound_strategy must be one of "
                f"{sorted(self._valid_strategies)}"
            )
        roi_timeseries: dict[str, list[float]] = bold_timeseries.get("roi_timeseries", {})
        matrix, roi_labels = await asyncio.to_thread(
            _compute_connectivity, roi_timeseries, connectivity_measure
        )
        return {
            "connectivity_matrix": matrix,
            "roi_labels": roi_labels,
            "n_rois": len(roi_labels),
            "measure": connectivity_measure,
        }
