"""``ConfusionMatrixAnalyzer`` — Knot that computes the confusion matrix
and per-class precision, recall, and F1 with macro/weighted averages.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.trained_model import TrainedModel


class ConfusionMatrixAnalyzer(Knot):
    """Compute confusion matrix and per-class classification metrics."""

    def __init__(
        self,
        *,
        model: Knot,
        split: Knot,
        class_labels: Sequence[str] | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(model, Knot):
            raise TypeError("ConfusionMatrixAnalyzer: model must be a Knot")
        if not isinstance(split, Knot):
            raise TypeError("ConfusionMatrixAnalyzer: split must be a Knot")
        self._class_labels: tuple[str, ...] | None = (
            tuple(class_labels) if class_labels is not None else None
        )
        super().__init__(model=model, split=split, _config=_config, **kwargs)

    async def process(
        self, model: TrainedModel, split: DataSplit, **_: Any
    ) -> Mapping[str, Any]:
        """Compute the confusion matrix and per-class metrics for the model on the test split.

        Args:
            model: TrainedModel reference to evaluate.
            split: DataSplit whose test partition is used for predictions.

        Returns:
            Mapping with ``confusion_matrix`` (list[list[float]]),
            ``per_class`` (dict with precision/recall/f1 per class),
            ``macro_f1`` (float), and ``weighted_f1`` (float).
        """
        labels = self._class_labels or ("class_0", "class_1")
        n = len(labels)
        matrix = [
            [
                self._cell_value(model, split, i, j)
                for j in range(n)
            ]
            for i in range(n)
        ]
        per_class: dict[str, dict[str, float]] = {}
        for idx, label in enumerate(labels):
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
        model: TrainedModel,
        split: DataSplit,
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
        model: TrainedModel,
        split: DataSplit,
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
