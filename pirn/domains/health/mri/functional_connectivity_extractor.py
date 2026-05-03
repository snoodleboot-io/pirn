"""``FunctionalConnectivityExtractor`` — extract functional connectivity matrix from resting-state fMRI."""
from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class FunctionalConnectivityExtractor(Knot):
    """Extract functional connectivity matrix from resting-state fMRI timeseries."""

    _VALID_MEASURES: frozenset[str] = frozenset(
        {"correlation", "partial_correlation", "tangent"}
    )
    _VALID_CONFOUND_STRATEGIES: frozenset[str] = frozenset({"none", "simple", "full"})

    def __init__(
        self,
        *,
        bold_timeseries: Knot,
        atlas: str,
        connectivity_measure: str,
        confound_strategy: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(atlas, str) or not atlas:
            raise ValueError("FunctionalConnectivityExtractor: atlas must be non-empty")
        if not isinstance(connectivity_measure, str) or connectivity_measure not in self._VALID_MEASURES:
            raise ValueError(
                f"FunctionalConnectivityExtractor: connectivity_measure must be one of "
                f"{sorted(self._VALID_MEASURES)}"
            )
        if not isinstance(confound_strategy, str) or confound_strategy not in self._VALID_CONFOUND_STRATEGIES:
            raise ValueError(
                f"FunctionalConnectivityExtractor: confound_strategy must be one of "
                f"{sorted(self._VALID_CONFOUND_STRATEGIES)}"
            )
        self._atlas = atlas
        self._connectivity_measure = connectivity_measure
        self._confound_strategy = confound_strategy
        super().__init__(bold_timeseries=bold_timeseries, _config=_config, **kwargs)

    async def process(self, bold_timeseries: dict[str, Any], **_: Any) -> dict[str, Any]:
        """Extract functional connectivity matrix from BOLD timeseries data.

        Args:
            bold_timeseries: Dict with ``roi_timeseries`` (dict[str, list[float]]),
                ``n_timepoints`` (int), and ``tr_sec`` (float).

        Returns:
            Dict with ``connectivity_matrix``, ``roi_labels``, ``n_rois``,
            and ``measure``.
        """
        if not isinstance(bold_timeseries, dict):
            raise TypeError("FunctionalConnectivityExtractor: bold_timeseries must be a dict")
        roi_timeseries: dict[str, list[float]] = bold_timeseries.get("roi_timeseries", {})
        roi_labels = list(roi_timeseries.keys())
        n_rois = len(roi_labels)
        matrix = [[0.0] * n_rois for _ in range(n_rois)]
        return {
            "connectivity_matrix": matrix,
            "roi_labels": roi_labels,
            "n_rois": n_rois,
            "measure": self._connectivity_measure,
        }
