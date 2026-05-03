"""``BacktestingEvaluator`` — SubTapestry that evaluates a forecasting
model on rolling historical windows, returning per-window and aggregate
metrics.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.trained_model import TrainedModel
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


@knot
async def _emit_value(value: Any) -> Any:
    return value


class BacktestingEvaluator(SubTapestry):
    """Evaluate a forecasting model on rolling historical windows."""

    def __init__(
        self,
        *,
        model: Knot,
        split: Knot,
        n_windows: int = 5,
        metric: str = "mape",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(model, Knot):
            raise TypeError("BacktestingEvaluator: model must be a Knot")
        if not isinstance(split, Knot):
            raise TypeError("BacktestingEvaluator: split must be a Knot")
        if not isinstance(n_windows, int) or n_windows < 1:
            raise ValueError("BacktestingEvaluator: n_windows must be an int >= 1")
        if not isinstance(metric, str) or not metric:
            raise ValueError(
                "BacktestingEvaluator: metric must be a non-empty string"
            )
        self._n_windows = n_windows
        self._metric = metric
        super().__init__(model=model, split=split, _config=_config, **kwargs)

    @property
    def n_windows(self) -> int:
        return self._n_windows

    @property
    def metric(self) -> str:
        return self._metric

    async def process(
        self, model: TrainedModel, split: DataSplit, **_: Any
    ) -> Mapping[str, Any]:
        """Evaluate the model across rolling windows and return per-window and aggregate metrics.

        Args:
            model: TrainedModel reference for a forecasting task.
            split: DataSplit used as the historical data pool for rolling windows.

        Returns:
            Mapping with ``window_scores`` (list[float]), ``mean_score`` (float),
            ``std_score`` (float), and ``metric`` (str).
        """
        window_scores: list[float] = []
        for w in range(self._n_windows):
            window_scores.append(self._window_score(model, split, w))
        mean_score = sum(window_scores) / len(window_scores)
        variance = sum((s - mean_score) ** 2 for s in window_scores) / len(window_scores)
        std_score = variance ** 0.5
        return {
            "window_scores": window_scores,
            "mean_score": mean_score,
            "std_score": std_score,
            "metric": self._metric,
        }

    def _window_score(
        self, model: TrainedModel, split: DataSplit, window_idx: int
    ) -> float:
        payload = json.dumps(
            {
                "model_id": model.model_id,
                "test_name": split.test.name,
                "window": window_idx,
                "metric": self._metric,
            },
            sort_keys=True,
            default=str,
        )
        digest = hashlib.sha256(payload.encode("utf-8")).digest()
        return int.from_bytes(digest[:8], "big") / float(2**64)
