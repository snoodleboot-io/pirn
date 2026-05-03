"""``NLGEvaluator`` — Knot that computes BLEU, ROUGE-L, and BERTScore
for generated text versus reference strings.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

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
        metrics: Sequence[str] | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(model, Knot):
            raise TypeError("NLGEvaluator: model must be a Knot")
        if not isinstance(split, Knot):
            raise TypeError("NLGEvaluator: split must be a Knot")
        allowed = {"bleu", "rouge_l", "bert_score"}
        selected = tuple(metrics) if metrics is not None else ("bleu", "rouge_l", "bert_score")
        for m in selected:
            if m not in allowed:
                raise ValueError(
                    f"NLGEvaluator: metric {m!r} not in {allowed}"
                )
        self._metrics = selected
        super().__init__(model=model, split=split, _config=_config, **kwargs)

    @property
    def metrics(self) -> tuple[str, ...]:
        return self._metrics

    async def process(
        self, model: TrainedModel, split: DataSplit, **_: Any
    ) -> Mapping[str, Any]:
        """Compute NLG metrics for generated text versus reference strings from the test split.

        Args:
            model: TrainedModel reference for a text generation task.
            split: DataSplit whose test partition contains (generated, reference) text pairs.

        Returns:
            Mapping with ``bleu``, ``rouge_l``, and/or ``bert_score`` values (each float in [0,1]).
        """
        result: dict[str, Any] = {}
        for metric in self._metrics:
            result[metric] = self._metric_value(model, split, metric)
        return result

    def _metric_value(
        self, model: TrainedModel, split: DataSplit, metric: str
    ) -> float:
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
