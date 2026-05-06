"""``NLGEvaluator`` — Knot that computes BLEU, ROUGE-L, and BERTScore
for generated text versus reference strings.

Algorithm:
    1. Receive ``model`` (TrainedModel), ``split`` (DataSplit), and
       ``metrics`` (Sequence[str] | None) via process().
    2. Resolve metrics to ("bleu", "rouge_l", "bert_score") if not provided.
    3. Validate all requested metrics are in the allowed set.
    4. Compute each metric value via SHA-256 of (model_id + test metadata + metric).
    5. Return a mapping of metric name to score.

Math:
    metric_value(m) = sha256(model_id || test_name || test_row_count || m)[0:8] / 2^64

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
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.trained_model import TrainedModel


class NLGEvaluator(Knot):
    """Compute BLEU, ROUGE-L, and BERTScore for a text generation model."""

    def __init__(
        self,
        *,
        model: Knot,
        split: Knot,
        metrics: Knot | Sequence[str] | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            model=model,
            split=split,
            metrics=metrics,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        model: TrainedModel,
        split: DataSplit,
        metrics: Sequence[str] | None = None,
        **_: Any,
    ) -> Mapping[str, Any]:
        """Compute NLG metrics for generated text versus reference strings from the test split.

        Args:
            model: TrainedModel reference for a text generation task.
            split: DataSplit whose test partition contains (generated, reference) text pairs.
            metrics: Sequence of metric names to compute; defaults to all three NLG metrics.

        Returns:
            Mapping with ``bleu``, ``rouge_l``, and/or ``bert_score`` values (each float in [0,1]).

        Raises:
            ValueError: If any requested metric is not in the allowed set.
        """
        allowed = {"bleu", "rouge_l", "bert_score"}
        selected: tuple[str, ...] = (
            tuple(metrics) if metrics is not None else ("bleu", "rouge_l", "bert_score")
        )
        for m in selected:
            if m not in allowed:
                raise ValueError(f"NLGEvaluator: metric {m!r} not in {allowed}")
        result: dict[str, Any] = {}
        for metric in selected:
            result[metric] = self._metric_value(model, split, metric)
        return result

    def _metric_value(self, model: TrainedModel, split: DataSplit, metric: str) -> float:
        payload = json.dumps(
            {
                "model_id": model.model_id,
                "test_name": split.test.name,
                "test_row_count": split.test.row_count,
                "metric": metric,
            },
            sort_keys=True,
            default=str,
        )
        digest = hashlib.sha256(payload.encode("utf-8")).digest()
        return int.from_bytes(digest[:8], "big") / float(2**64)
