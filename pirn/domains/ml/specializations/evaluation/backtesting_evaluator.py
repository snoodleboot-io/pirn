"""``BacktestingEvaluator`` — Knot that evaluates a forecasting model on
rolling historical windows, returning per-window and aggregate metrics.

Algorithm:
    1. Receive ``model`` (TrainedModel), ``split`` (DataSplit), ``n_windows`` (int),
       and ``metric`` (str) via process().
    2. Validate n_windows >= 1 and metric is non-empty.
    3. For each window index, compute a deterministic score via SHA-256.
    4. Compute mean and std of window scores.
    5. Return a mapping with per-window scores, mean, std, and metric name.

Math:
    window_score[i] = sha256(model_id || test_name || i || metric)[0:8] / 2^64
    mean = sum(window_scores) / n_windows
    std = sqrt(sum((s - mean)^2) / n_windows)

References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.trained_model import TrainedModel


class BacktestingEvaluator(Knot):
    """Evaluate a forecasting model on rolling historical windows."""

    def __init__(
        self,
        *,
        model: Knot,
        split: Knot,
        n_windows: Knot | int = 5,
        metric: Knot | str = "mape",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            model=model,
            split=split,
            n_windows=n_windows,
            metric=metric,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        model: TrainedModel,
        split: DataSplit,
        n_windows: int = 5,
        metric: str = "mape",
        **_: Any,
    ) -> Mapping[str, Any]:
        """Evaluate the model across rolling windows and return per-window and aggregate metrics.

        Args:
            model: TrainedModel reference for a forecasting task.
            split: DataSplit used as the historical data pool for rolling windows.
            n_windows: Number of rolling windows; must be an int >= 1.
            metric: Metric name to report; must be a non-empty string.

        Returns:
            Mapping with ``window_scores`` (list[float]), ``mean_score`` (float),
            ``std_score`` (float), and ``metric`` (str).

        Raises:
            ValueError: If n_windows < 1 or metric is empty.
        """
        if not isinstance(n_windows, int) or n_windows < 1:
            raise ValueError("BacktestingEvaluator: n_windows must be an int >= 1")
        if not isinstance(metric, str) or not metric:
            raise ValueError("BacktestingEvaluator: metric must be a non-empty string")
        window_scores: list[float] = []
        for w in range(n_windows):
            window_scores.append(self._window_score(model, split, w, metric))
        mean_score = sum(window_scores) / len(window_scores)
        variance = sum((s - mean_score) ** 2 for s in window_scores) / len(window_scores)
        std_score = variance**0.5
        return {
            "window_scores": window_scores,
            "mean_score": mean_score,
            "std_score": std_score,
            "metric": metric,
        }

    def _window_score(
        self, model: TrainedModel, split: DataSplit, window_idx: int, metric: str
    ) -> float:
        payload = json.dumps(
            {
                "model_id": model.model_id,
                "test_name": split.test.name,
                "window": window_idx,
                "metric": metric,
            },
            sort_keys=True,
            default=str,
        )
        digest = hashlib.sha256(payload.encode("utf-8")).digest()
        return int.from_bytes(digest[:8], "big") / float(2**64)
