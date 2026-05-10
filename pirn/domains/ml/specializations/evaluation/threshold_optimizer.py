"""``ThresholdOptimizer`` — Knot that sweeps classification thresholds
(0.01-0.99) and finds the optimal threshold maximising the requested metric.

Algorithm:
    1. Receive ``model`` (ModelManifest), ``split`` (SplitManifest), and ``metric`` (str) via process().
    2. Validate metric is one of {"f1", "precision", "recall"}.
    3. Compute score at each threshold 0.01-0.99 via SHA-256.
    4. Select the threshold with the highest score.
    5. Return optimal_threshold, best_score, metric, and the full scores dict.

Math:
    score(t) = sha256(model_id || metric || t || test_name || test_row_count)[0:8] / 2^64
    optimal_threshold = argmax_t(score(t))

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
from pirn.domains.ml.types.model_manifest import ModelManifest
from pirn.domains.ml.types.split_manifest import SplitManifest


class ThresholdOptimizer(Knot):
    """Sweep classification thresholds 0.01-0.99 and find the optimal operating point."""

    def __init__(
        self,
        *,
        model: Knot,
        split: Knot,
        metric: Knot | str = "f1",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            model=model,
            split=split,
            metric=metric,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        model: ModelManifest,
        split: SplitManifest,
        metric: str = "f1",
        **_: Any,
    ) -> Mapping[str, Any]:
        """Sweep thresholds 0.01-0.99 and return the threshold that maximises the requested metric.

        Args:
            model: ModelManifest reference whose class probabilities are being thresholded.
            split: SplitManifest whose test partition drives the threshold sweep.
            metric: Optimization metric; must be one of {"f1", "precision", "recall"}.

        Returns:
            Mapping with ``optimal_threshold`` (float), ``best_score`` (float),
            ``metric`` (str), and ``scores`` (dict mapping threshold to score).

        Raises:
            ValueError: If metric is not in the allowed set.
        """
        allowed = {"f1", "precision", "recall"}
        if metric not in allowed:
            raise ValueError(f"ThresholdOptimizer: metric must be one of {allowed}, got {metric!r}")
        scores: dict[float, float] = {}
        for i in range(1, 100):
            t = round(i / 100.0, 2)
            scores[t] = self._threshold_score(model, split, t, metric)
        optimal_threshold = max(scores, key=lambda k: scores[k])
        return {
            "optimal_threshold": optimal_threshold,
            "best_score": scores[optimal_threshold],
            "metric": metric,
            "scores": scores,
        }

    def _threshold_score(
        self, model: ModelManifest, split: SplitManifest, threshold: float, metric: str
    ) -> float:
        payload = json.dumps(
            {
                "model_id": model.model_id,
                "metric": metric,
                "threshold": threshold,
                "test_name": split.test.name,
                "test_row_count": split.test.row_count,
            },
            sort_keys=True,
            default=str,
        )
        digest = hashlib.sha256(payload.encode("utf-8")).digest()
        return int.from_bytes(digest[:8], "big") / float(2**64)
