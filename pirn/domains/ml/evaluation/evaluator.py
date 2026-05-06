"""``Evaluator`` — compute metrics for a :class:`TrainedModel` on a
:class:`DataSplit.test` slice.

The base class returns a deterministic :class:`EvalReport` so the
orchestration plan is well-formed offline. Concrete subclasses override
:meth:`_score` to perform a real fit/predict/score loop.

Algorithm:
    1. Receive ``model`` (TrainedModel), ``split`` (DataSplit), and ``metrics``
       (sequence of str) via process().
    2. Validate that metrics is non-empty and all elements are non-empty strings.
    3. For each metric, compute a deterministic score via SHA-256(model_id + metric + split).
    4. Wrap scores in an EvalReport and return.

Math:
    score[metric] = sha256(model_id || metric || test_name || test_row_count)[0:8] as uint64 / 2^64

References:
    N/A — pirn-native implementation.
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
        metrics: Knot | Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(model=model, split=split, metrics=metrics, _config=_config, **kwargs)

    async def process(
        self, model: TrainedModel, split: DataSplit, metrics: Sequence[str] = (), **_: Any
    ) -> EvalReport:
        """Compute each configured metric for the model on the test split and return an EvalReport.

        Args:
            model: TrainedModel reference to evaluate.
            split: DataSplit whose test partition is used for scoring.
            metrics: Non-empty sequence of metric name strings.

        Returns:
            EvalReport containing all configured metrics and evaluation metadata.

        Raises:
            ValueError: If metrics is empty or any element is not a non-empty string.
        """
        metric_tuple = tuple(metrics)
        if not metric_tuple:
            raise ValueError("Evaluator: metrics must be non-empty")
        for metric in metric_tuple:
            if not isinstance(metric, str) or not metric:
                raise ValueError(
                    "Evaluator: every metric name must be a non-empty string"
                )
        scored = MappingProxyType(
            {metric: self._score(model, split, metric) for metric in metric_tuple}
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

