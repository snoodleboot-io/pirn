"""``Evaluator`` — compute metrics for a :class:`TrainedModel` on a
:class:`DataSplit.test` slice.

The base class returns a deterministic :class:`EvalReport` so the
orchestration plan is well-formed offline. Concrete subclasses override
:meth:`_score` to perform a real fit/predict/score loop.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.eval_report import EvalReport
from pirn.domains.ml.types.trained_model import TrainedModel


class Evaluator(Knot):
    """Compute a metric report for a model on a test partition."""

    def __init__(
        self,
        *,
        model: Knot,
        split: Knot,
        metrics: Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        metric_tuple = tuple(metrics)
        if not metric_tuple:
            raise ValueError("Evaluator: metrics must be non-empty")
        for metric in metric_tuple:
            if not isinstance(metric, str) or not metric:
                raise ValueError(
                    "Evaluator: every metric name must be a non-empty string"
                )
        self._metrics = metric_tuple
        super().__init__(model=model, split=split, _config=_config, **kwargs)

    @property
    def metrics(self) -> tuple[str, ...]:
        return self._metrics

    async def process(
        self, model: TrainedModel, split: DataSplit, **_: Any
    ) -> EvalReport:
        """Compute each configured metric for the model on the test split and return an EvalReport.

        Args:
            model: TrainedModel reference to evaluate.
            split: DataSplit whose test partition is used for scoring.

        Returns:
            EvalReport containing all configured metrics and evaluation metadata.
        """
        scored = MappingProxyType(
            {metric: self._score(model, split, metric) for metric in self._metrics}
        )
        return EvalReport(
            model_id=model.model_id,
            metrics=scored,
            dataset_name=split.test.name,
            evaluated_at=datetime.now(timezone.utc),
            details=MappingProxyType(
                {
                    "algorithm": model.algorithm,
                    "test_row_count": split.test.row_count,
                }
            ),
        )

    def _score(
        self, model: TrainedModel, split: DataSplit, metric: str
    ) -> float:
        payload = json.dumps(
            {
                "model_id": model.model_id,
                "metric": metric,
                "test_name": split.test.name,
                "test_row_count": split.test.row_count,
            },
            sort_keys=True,
            default=str,
        )
        digest = hashlib.sha256(payload.encode("utf-8")).digest()
        return int.from_bytes(digest[:8], "big") / float(2**64)
