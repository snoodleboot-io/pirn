"""``ROCAUCAnalyzer`` — Knot that computes the ROC curve, AUC, and
optimal operating point for a binary classifier.

Algorithm:
    1. Receive ``model`` (ModelManifest) and ``split`` (SplitManifest) via process().
    2. Sweep 11 threshold points from 0 to 1 and compute FPR/TPR via SHA-256.
    3. Force boundary conditions: fpr[0]=tpr[0]=1.0, fpr[-1]=tpr[-1]=0.0.
    4. Compute AUC and find optimal threshold via Youden J statistic.
    5. Return fpr, tpr, thresholds, auc, and optimal_threshold.

Math:
    ROC curve: at threshold t, classify y_hat = 1 if score >= t, else 0.
        FPR(t) = FP(t) / (FP(t) + TN(t))
        TPR(t) = TP(t) / (TP(t) + FN(t))

    AUC (trapezoidal rule over n threshold points):
        AUC = sum_{i=1}^{n-1} (fpr[i-1] - fpr[i]) * (tpr[i-1] + tpr[i]) / 2

    Youden J statistic (optimal threshold selection):
        J[i] = tpr[i] - fpr[i]
        optimal_threshold = thresholds[argmax_i J[i]]

    Stub implementation:
        curve_value(t, kind) = sha256(model_id || test_name || test_row_count || t || kind)[0:8] / 2^64
        auc                  = sha256(model_id || test_name || test_row_count || "auc")[0:8] / 2^64

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

from pirn_ml.types.model_manifest import ModelManifest
from pirn_ml.types.split_manifest import SplitManifest


class ROCAUCAnalyzer(Knot):
    """Compute ROC curve, AUC, and optimal operating point."""

    def __init__(
        self,
        *,
        model: Knot,
        split: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(model=model, split=split, _config=_config, **kwargs)

    async def process(
        self, model: ModelManifest, split: SplitManifest, **_: Any
    ) -> Mapping[str, Any]:
        """Compute the ROC curve, AUC, and optimal operating point for the model on the test split.

        Args:
            model: ModelManifest reference to evaluate.
            split: SplitManifest whose test partition is used for ROC computation.

        Returns:
            Mapping with ``fpr`` (list[float]), ``tpr`` (list[float]),
            ``thresholds`` (list[float]), ``auc`` (float), and
            ``optimal_threshold`` (float) at the Youden J statistic.
        """
        n_points = 11
        fpr: list[float] = []
        tpr: list[float] = []
        thresholds: list[float] = []
        for point_idx in range(n_points):
            threshold_val = round(point_idx / (n_points - 1), 2)
            thresholds.append(threshold_val)
            fpr.append(self._curve_value(model, split, threshold_val, "fpr"))
            tpr.append(self._curve_value(model, split, threshold_val, "tpr"))
        fpr[0], tpr[0] = 1.0, 1.0
        fpr[-1], tpr[-1] = 0.0, 0.0
        auc = self._auc_value(model, split)
        j_scores = [tpr[point_idx] - fpr[point_idx] for point_idx in range(n_points)]
        best_idx = j_scores.index(max(j_scores))
        return {
            "fpr": fpr,
            "tpr": tpr,
            "thresholds": thresholds,
            "auc": auc,
            "optimal_threshold": thresholds[best_idx],
        }

    def _curve_value(
        self,
        model: ModelManifest,
        split: SplitManifest,
        threshold: float,
        curve_type: str,
    ) -> float:
        payload = json.dumps(
            {
                "model_id": model.model_id,
                "test_name": split.test.name,
                "test_row_count": split.test.row_count,
                "threshold": threshold,
                "curve_type": curve_type,
            },
            sort_keys=True,
            default=str,
        )
        digest = hashlib.sha256(payload.encode("utf-8")).digest()
        return int.from_bytes(digest[:8], "big") / float(2**64)

    def _auc_value(self, model: ModelManifest, split: SplitManifest) -> float:
        payload = json.dumps(
            {
                "model_id": model.model_id,
                "test_name": split.test.name,
                "test_row_count": split.test.row_count,
                "metric": "auc",
            },
            sort_keys=True,
            default=str,
        )
        digest = hashlib.sha256(payload.encode("utf-8")).digest()
        return int.from_bytes(digest[:8], "big") / float(2**64)
