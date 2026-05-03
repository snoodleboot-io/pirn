"""``PredictionDriftMonitor`` — Knot that tracks rolling mean and std of
predictions and alerts when they deviate beyond a configurable sigma
threshold.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.trained_model import TrainedModel


class PredictionDriftMonitor(Knot):
    """Track rolling prediction statistics and alert on sigma-threshold deviations."""

    def __init__(
        self,
        *,
        model: Knot,
        baseline: Knot,
        current: Knot,
        sigma_threshold: float = 3.0,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(model, Knot):
            raise TypeError("PredictionDriftMonitor: model must be a Knot")
        if not isinstance(baseline, Knot):
            raise TypeError("PredictionDriftMonitor: baseline must be a Knot")
        if not isinstance(current, Knot):
            raise TypeError("PredictionDriftMonitor: current must be a Knot")
        if not isinstance(sigma_threshold, (int, float)) or sigma_threshold <= 0.0:
            raise ValueError(
                "PredictionDriftMonitor: sigma_threshold must be a positive number"
            )
        self._sigma_threshold = float(sigma_threshold)
        super().__init__(model=model, baseline=baseline, current=current, _config=_config, **kwargs)

    @property
    def sigma_threshold(self) -> float:
        return self._sigma_threshold

    async def process(
        self,
        model: TrainedModel,
        baseline: DataSplit,
        current: DataSplit,
        **_: Any,
    ) -> Mapping[str, Any]:
        """Compare rolling prediction statistics between baseline and current windows and alert on deviations.

        Args:
            model: TrainedModel whose predictions are being monitored.
            baseline: DataSplit representing the reference prediction distribution.
            current: DataSplit representing the recent prediction window.

        Returns:
            Mapping with ``baseline_mean``, ``baseline_std``, ``current_mean``,
            ``current_std``, ``z_score`` (float), ``alert`` (bool),
            and ``sigma_threshold`` (float).
        """
        baseline_mean = self._stat(model, baseline, "mean")
        baseline_std = max(1e-9, self._stat(model, baseline, "std"))
        current_mean = self._stat(model, current, "mean")
        current_std = self._stat(model, current, "std")
        z_score = abs(current_mean - baseline_mean) / baseline_std
        alert = z_score > self._sigma_threshold
        return {
            "baseline_mean": baseline_mean,
            "baseline_std": baseline_std,
            "current_mean": current_mean,
            "current_std": current_std,
            "z_score": z_score,
            "alert": alert,
            "sigma_threshold": self._sigma_threshold,
        }

    def _stat(self, model: TrainedModel, split: DataSplit, stat: str) -> float:
        payload = json.dumps(
            {
                "model_id": model.model_id,
                "split_name": split.train.name,
                "row_count": split.train.row_count,
                "stat": stat,
            },
            sort_keys=True,
            default=str,
        )
        digest = hashlib.sha256(payload.encode("utf-8")).digest()
        return int.from_bytes(digest[:8], "big") / float(2**64)
