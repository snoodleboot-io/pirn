"""``ThresholdOptimizer`` — Knot that sweeps classification thresholds
(0.01–0.99) and finds the optimal threshold maximising the requested metric.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.trained_model import TrainedModel


class ThresholdOptimizer(Knot):
    """Sweep classification thresholds 0.01–0.99 and find the optimal operating point."""

    def __init__(
        self,
        *,
        model: Knot,
        split: Knot,
        metric: str = "f1",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        allowed = {"f1", "precision", "recall"}
        if metric not in allowed:
            raise ValueError(
                f"ThresholdOptimizer: metric must be one of {allowed}, got {metric!r}"
            )
        self._metric = metric
        super().__init__(model=model, split=split, _config=_config, **kwargs)

    @property
    def metric(self) -> str:
        return self._metric

    async def process(
        self, model: TrainedModel, split: DataSplit, **_: Any
    ) -> Mapping[str, Any]:
        """Sweep thresholds 0.01–0.99 and return the threshold that maximises the configured metric.

        Args:
            model: TrainedModel reference whose class probabilities are being thresholded.
            split: DataSplit whose test partition drives the threshold sweep.

        Returns:
            Mapping with ``optimal_threshold`` (float), ``best_score`` (float),
            ``metric`` (str), and ``scores`` (dict mapping threshold to score).
        """
        scores: dict[float, float] = {}
        for i in range(1, 100):
            t = round(i / 100.0, 2)
            scores[t] = self._threshold_score(model, split, t)
        optimal_threshold = max(scores, key=lambda k: scores[k])
        return {
            "optimal_threshold": optimal_threshold,
            "best_score": scores[optimal_threshold],
            "metric": self._metric,
            "scores": scores,
        }

    def _threshold_score(
        self, model: TrainedModel, split: DataSplit, threshold: float
    ) -> float:
        payload = json.dumps(
            {
                "model_id": model.model_id,
                "metric": self._metric,
                "threshold": threshold,
                "test_name": split.test.name,
                "test_row_count": split.test.row_count,
            },
            sort_keys=True,
            default=str,
        )
        digest = hashlib.sha256(payload.encode("utf-8")).digest()
        return int.from_bytes(digest[:8], "big") / float(2**64)
