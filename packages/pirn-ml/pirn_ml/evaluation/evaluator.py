"""``Evaluator`` — compute metrics for a :class:`ModelManifest` on a
:class:`SplitManifest.test` slice.

The base class returns a deterministic :class:`EvalMetadata` so the
orchestration plan is well-formed offline. Concrete subclasses override
:meth:`_score` to perform a real fit/predict/score loop.

Algorithm:
    1. Receive ``model`` (ModelManifest), ``split`` (SplitManifest), and ``metrics``
       (sequence of str) via process().
    2. Validate that metrics is non-empty and all elements are non-empty strings.
    3. For each metric, compute a deterministic score via SHA-256(model_id + metric + split).
    4. Wrap scores in an EvalMetadata and return.

Math:
    score[metric] = sha256(model_id || metric || test_name || test_row_count)[0:8] as uint64 / 2^64

References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_ml.types.eval_metadata import EvalMetadata
from pirn_ml.types.eval_metrics import EvalMetrics
from pirn_ml.types.eval_report_payload import EvalReportPayload
from pirn_ml.types.model_manifest import ModelManifest
from pirn_ml.types.split_manifest import SplitManifest


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
        self, model: ModelManifest, split: SplitManifest, metrics: Sequence[str] = (), **_: Any
    ) -> EvalReportPayload:
        """Compute each configured metric for the model on the test split and return an EvalReportPayload.

        Args:
            model: ModelManifest reference to evaluate.
            split: SplitManifest whose test partition is used for scoring.
            metrics: Non-empty sequence of metric name strings.

        Returns:
            EvalReportPayload containing all configured metrics and evaluation metadata.

        Raises:
            ValueError: If metrics is empty or any element is not a non-empty string.
        """
        metric_tuple = tuple(metrics)
        if not metric_tuple:
            raise ValueError("Evaluator: metrics must be non-empty")
        for metric in metric_tuple:
            if not isinstance(metric, str) or not metric:
                raise ValueError("Evaluator: every metric name must be a non-empty string")
        scored = MappingProxyType(
            {metric: self._score(model, split, metric) for metric in metric_tuple}
        )
        return EvalReportPayload(
            metadata=EvalMetadata(
                model_id=model.model_id,
                dataset_name=split.test.name,
                evaluated_at=datetime.now(UTC),
            ),
            data=EvalMetrics(
                scores=scored,
                details=MappingProxyType(
                    {
                        "algorithm": model.algorithm,
                        "test_row_count": split.test.row_count,
                    }
                ),
            ),
        )

    def _score(self, model: ModelManifest, split: SplitManifest, metric: str) -> float:
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
