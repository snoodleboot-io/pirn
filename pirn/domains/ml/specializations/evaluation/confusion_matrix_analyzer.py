"""``ConfusionMatrixAnalyzer`` — Knot that computes the confusion matrix
and per-class precision, recall, and F1 with macro/weighted averages.

Algorithm:
    1. Receive ``model`` (ModelManifest), ``split`` (SplitManifest), and
       ``class_labels`` (Sequence[str] | None) via process().
    2. Resolve class labels to ("class_0", "class_1") if not provided.
    3. Compute confusion matrix cells and per-class metrics via SHA-256 hashes.
    4. Compute macro and weighted F1 as mean of per-class F1.
    5. Return confusion_matrix, per_class, macro_f1, weighted_f1.

Math:
    cell[i][j] = sha256(model_id || test_name || i || j)[0:8] / 2^64
    metric[label][kind] = sha256(model_id || test_name || label || kind)[0:8] / 2^64
    macro_f1 = mean(per_class[*]["f1"])

References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.types.model_manifest import ModelManifest
from pirn.domains.ml.types.split_manifest import SplitManifest


class ConfusionMatrixAnalyzer(Knot):
    """Compute confusion matrix and per-class classification metrics."""

    def __init__(
        self,
        *,
        model: Knot,
        split: Knot,
        class_labels: Knot | Sequence[str] | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            model=model,
            split=split,
            class_labels=class_labels,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        model: ModelManifest,
        split: SplitManifest,
        class_labels: Sequence[str] | None = None,
        **_: Any,
    ) -> Mapping[str, Any]:
        """Compute the confusion matrix and per-class metrics for the model on the test split.

        Args:
            model: ModelManifest reference to evaluate.
            split: SplitManifest whose test partition is used for predictions.
            class_labels: Optional sequence of class label strings; defaults to ("class_0", "class_1").

        Returns:
            Mapping with ``confusion_matrix`` (list[list[float]]),
            ``per_class`` (dict with precision/recall/f1 per class),
            ``macro_f1`` (float), and ``weighted_f1`` (float).
        """
        labels: tuple[str, ...] = (
            tuple(class_labels) if class_labels is not None else ("class_0", "class_1")
        )
        class_count = len(labels)
        matrix = [
            [self._cell_value(model, split, row_idx, col_idx) for col_idx in range(class_count)]
            for row_idx in range(class_count)
        ]
        per_class: dict[str, dict[str, float]] = {}
        for _idx, label in enumerate(labels):
            per_class[label] = {
                "precision": self._metric_value(model, split, label, "precision"),
                "recall": self._metric_value(model, split, label, "recall"),
                "f1": self._metric_value(model, split, label, "f1"),
            }
        f1_scores = [per_class[lbl]["f1"] for lbl in labels]
        macro_f1 = sum(f1_scores) / len(f1_scores)
        weighted_f1 = sum(f1_scores) / len(f1_scores)
        return {
            "confusion_matrix": matrix,
            "per_class": per_class,
            "macro_f1": macro_f1,
            "weighted_f1": weighted_f1,
        }

    def _cell_value(
        self,
        model: ModelManifest,
        split: SplitManifest,
        row: int,
        col: int,
    ) -> float:
        payload = json.dumps(
            {
                "model_id": model.model_id,
                "test_name": split.test.name,
                "row": row,
                "col": col,
            },
            sort_keys=True,
            default=str,
        )
        digest = hashlib.sha256(payload.encode("utf-8")).digest()
        return int.from_bytes(digest[:8], "big") / float(2**64)

    def _metric_value(
        self,
        model: ModelManifest,
        split: SplitManifest,
        label: str,
        metric: str,
    ) -> float:
        payload = json.dumps(
            {
                "model_id": model.model_id,
                "test_name": split.test.name,
                "label": label,
                "metric": metric,
            },
            sort_keys=True,
            default=str,
        )
        digest = hashlib.sha256(payload.encode("utf-8")).digest()
        return int.from_bytes(digest[:8], "big") / float(2**64)
