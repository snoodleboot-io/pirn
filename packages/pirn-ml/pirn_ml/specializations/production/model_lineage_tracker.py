"""``ModelLineageTracker`` — Knot that records the full lineage
chain for a (dataset, split, model, report) tuple to a
:class:`LineageStore`.

The tracker emits one event per stage and returns the lineage id (a
deterministic digest of the resolved model + dataset metadata) so
downstream knots can attach the chain to a deployment record.

Algorithm:
    1. Receive ``dataset``, ``split``, ``model``, ``report``, and
       ``lineage`` via process().
    2. Validate all inputs.
    3. Compute deterministic lineage_id from dataset/model/report metadata.
    4. Log lineage events to the LineageStore.
    5. Return lineage_id.


References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_ml.lineage_store import LineageStore
from pirn_ml.types.dataset_manifest import DatasetManifest
from pirn_ml.types.eval_report_payload import EvalReportPayload
from pirn_ml.types.model_manifest import ModelManifest
from pirn_ml.types.split_manifest import SplitManifest


class ModelLineageTracker(Knot):
    """Record dataset → split → model → report into a lineage store."""

    def __init__(
        self,
        *,
        dataset: Knot,
        split: Knot,
        model: Knot,
        report: Knot,
        lineage: Knot | LineageStore,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            dataset=dataset,
            split=split,
            model=model,
            report=report,
            lineage=lineage,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        dataset: DatasetManifest,
        split: SplitManifest,
        model: ModelManifest,
        report: EvalReportPayload,
        lineage: LineageStore | None = None,
        **_: Any,
    ) -> str:
        """Record dataset, split, model, and report as lineage events and return the deterministic lineage_id.

        Args:
            dataset: DatasetManifest whose metadata is hashed into the lineage chain.
            split: SplitManifest whose train/test partition names are recorded.
            model: ModelManifest whose model_id and algorithm are logged.
            report: EvalMetadata whose metrics are captured in the lineage event.
            lineage: LineageStore to record the events into.

        Returns:
            Deterministic 32-character hex lineage identifier derived from the
            dataset hash, model_id, report metrics, and recording timestamp.

        Raises:
            TypeError: If lineage is not a LineageStore.
        """
        if not isinstance(lineage, LineageStore):
            raise TypeError("ModelLineageTracker: lineage must be a LineageStore")
        recorded_at = datetime.now(UTC).isoformat()
        dataset_hash = self._hash(
            {
                "name": dataset.name,
                "row_count": dataset.row_count,
                "feature_names": list(dataset.feature_names),
                "target_name": dataset.target_name,
                "source_uri": dataset.source_uri,
            }
        )
        lineage_id = self._hash(
            {
                "dataset_hash": dataset_hash,
                "model_id": model.model_id,
                "report_metrics": dict(report.metrics.scores),
                "recorded_at": recorded_at,
            }
        )
        await lineage.log_event(
            "dataset_observed",
            {
                "lineage_id": lineage_id,
                "dataset_hash": dataset_hash,
                "name": dataset.name,
                "row_count": dataset.row_count,
                "recorded_at": recorded_at,
            },
        )
        await lineage.log_event(
            "split_observed",
            {
                "lineage_id": lineage_id,
                "train_name": split.train.name,
                "test_name": split.test.name,
                "validation_name": (split.validation.name if split.validation else None),
                "recorded_at": recorded_at,
            },
        )
        await lineage.log_event(
            "model_observed",
            {
                "lineage_id": lineage_id,
                "model_id": model.model_id,
                "algorithm": model.algorithm,
                "recorded_at": recorded_at,
            },
        )
        await lineage.log_event(
            "report_observed",
            {
                "lineage_id": lineage_id,
                "model_id": model.model_id,
                "metrics": {k: float(v) for k, v in report.metrics.scores.items()},
                "dataset_name": report.report.dataset_name,
                "recorded_at": recorded_at,
            },
        )
        return lineage_id

    def _hash(self, payload: dict[str, Any]) -> str:
        encoded = json.dumps(payload, sort_keys=True, default=str)
        digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        return digest[:32]
