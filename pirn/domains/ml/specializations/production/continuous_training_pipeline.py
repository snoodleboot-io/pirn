"""``ContinuousTrainingPipeline`` — scheduled re-training SubTapestry.

Same composition as :class:`FullTrainDeployPipeline` but designed to be
re-run on a cadence. Before retraining the pipeline performs a freshness
check against the configured :class:`LineageStore`: if the last training
event is younger than ``freshness_window_days`` the pipeline short-circuits
and returns the cached model id without retraining.

Algorithm:
    1. Receive all pipeline params via process().
    2. Validate all inputs.
    3. Check freshness via lineage store; return cached model_id if fresh.
    4. Wire full training pipeline in an inner Tapestry.
    5. Run via _run_inner() and return model_id and eval_report.


References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.domains.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.domains.connectors.object_store import ObjectStore
from pirn.domains.ml.data_prep.dataset_loader import DatasetLoader
from pirn.domains.ml.data_prep.train_test_split import TrainTestSplit
from pirn.domains.ml.deployment.model_registrar import ModelRegistrar
from pirn.domains.ml.deployment.model_serializer import ModelSerializer
from pirn.domains.ml.deployment.predictor import Predictor
from pirn.domains.ml.evaluation.evaluator import Evaluator
from pirn.domains.ml.lineage_store import LineageStore
from pirn.domains.ml.training.trainer import Trainer
from pirn.domains.ml.types.eval_report_payload import EvalReportPayload
from pirn.domains.ml.types.split_manifest import SplitManifest
from pirn.nodes.sub_tapestry import SubTapestry


@knot
async def _holdout_features(split: SplitManifest) -> list[Mapping[str, Any]]:
    rows = []
    for index in range(int(split.test.row_count)):
        row: dict[str, Any] = {feature: float(index) for feature in split.test.feature_names}
        rows.append(row)
    return rows


@knot
async def _emit_value(value: Any) -> Any:
    return value


@knot
async def _combine_continuous_training(
    model_id: str,
    eval_report: EvalReportPayload,
) -> Mapping[str, Any]:
    return {"model_id": model_id, "eval_report": eval_report, "skipped": False}


class ContinuousTrainingPipeline(SubTapestry):
    """Scheduled retraining SubTapestry with a freshness gate."""

    def __init__(
        self,
        *,
        pool: Knot | DatabaseConnectionPool,
        query: Knot | str,
        name: Knot | str,
        feature_names: Knot | Sequence[str],
        target_name: Knot | str,
        algorithm: Knot | str,
        lineage: Knot | LineageStore,
        store: Knot | ObjectStore,
        metrics: Knot | Sequence[str],
        freshness_window_days: Knot | int = 1,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            pool=pool,
            query=query,
            name=name,
            feature_names=feature_names,
            target_name=target_name,
            algorithm=algorithm,
            lineage=lineage,
            store=store,
            metrics=metrics,
            freshness_window_days=freshness_window_days,
            _config=_config,
            **kwargs,
        )

    async def _is_fresh(
        self, lineage: LineageStore, name: str, freshness_window_days: int
    ) -> tuple[bool, str | None]:
        try:
            lineage_record = await lineage.fetch_lineage(name)
        except Exception:
            return False, None
        if not isinstance(lineage_record, Mapping) or "events" not in lineage_record:
            raise ValueError(
                "ContinuousTrainingPipeline: lineage record missing required field 'events'"
            )
        events = lineage_record["events"]
        if not events:
            return False, None
        last_event = events[-1]
        if not isinstance(last_event, Mapping):
            return False, None
        recorded_at = last_event.get("recorded_at")
        last_model_id = last_event.get("model_id")
        if not isinstance(recorded_at, str) or not isinstance(last_model_id, str):
            return False, None
        try:
            recorded = datetime.fromisoformat(recorded_at)
        except ValueError:
            return False, None
        now = datetime.now(UTC)
        if recorded.tzinfo is None:
            recorded = recorded.replace(tzinfo=UTC)
        if now - recorded < timedelta(days=freshness_window_days):
            return True, last_model_id
        return False, None

    async def process(
        self,
        pool: DatabaseConnectionPool | None = None,
        query: str = "",
        name: str = "",
        feature_names: Sequence[str] = (),
        target_name: str = "",
        algorithm: str = "",
        lineage: LineageStore | None = None,
        store: ObjectStore | None = None,
        metrics: Sequence[str] = (),
        freshness_window_days: int = 1,
        **_: Any,
    ) -> Any:
        """Check freshness against the lineage store and, if stale, retrain and deploy the model; return a summary with the model_id and eval report.

        Args:
            pool: DatabaseConnectionPool for loading the dataset.
            query: Non-empty SQL query string.
            name: Non-empty dataset/pipeline name.
            feature_names: Non-empty sequence of feature column names.
            target_name: Non-empty target column name.
            algorithm: Non-empty algorithm identifier.
            lineage: LineageStore for freshness checks and registration.
            store: ObjectStore for model artifact storage.
            metrics: Non-empty sequence of metric names.
            freshness_window_days: Retraining skip window in days; must be int >= 0.

        Returns:
            Mapping with ``model_id`` (str), ``eval_report``
            (:class:`EvalMetadata` or ``None`` if skipped), and ``skipped``
            (bool indicating whether retraining was bypassed due to freshness).

        Raises:
            ValueError: If any string param is empty or sequences are empty.
            TypeError: If pool, lineage, or store are the wrong types.
        """
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError("ContinuousTrainingPipeline: pool must be a DatabaseConnectionPool")
        if not isinstance(query, str) or not query:
            raise ValueError("ContinuousTrainingPipeline: query must be a non-empty string")
        if not isinstance(name, str) or not name:
            raise ValueError("ContinuousTrainingPipeline: name must be a non-empty string")
        feature_tuple = tuple(feature_names)
        if not feature_tuple:
            raise ValueError("ContinuousTrainingPipeline: feature_names must be non-empty")
        if not isinstance(target_name, str) or not target_name:
            raise ValueError("ContinuousTrainingPipeline: target_name must be a non-empty string")
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError("ContinuousTrainingPipeline: algorithm must be a non-empty string")
        if not isinstance(lineage, LineageStore):
            raise TypeError("ContinuousTrainingPipeline: lineage must be a LineageStore")
        if not isinstance(store, ObjectStore):
            raise TypeError("ContinuousTrainingPipeline: store must be an ObjectStore")
        metric_tuple = tuple(metrics)
        if not metric_tuple:
            raise ValueError("ContinuousTrainingPipeline: metrics must be non-empty")
        if not isinstance(freshness_window_days, int):
            raise TypeError("ContinuousTrainingPipeline: freshness_window_days must be an int")
        if freshness_window_days < 0:
            raise ValueError("ContinuousTrainingPipeline: freshness_window_days must be >= 0")
        is_fresh, cached_model_id = await self._is_fresh(lineage, name, freshness_window_days)
        if is_fresh and cached_model_id is not None:
            return _emit_value(
                value={"model_id": cached_model_id, "eval_report": None, "skipped": True},
                _config=KnotConfig(id="skipped"),
            )
        dataset = DatasetLoader(
            name=name,
            feature_names=feature_tuple,
            target_name=target_name,
            pool=pool,
            query=query,
            _config=KnotConfig(id="load"),
        )
        split = TrainTestSplit(
            dataset=dataset,
            _config=KnotConfig(id="split"),
        )
        trained = Trainer(
            split=split,
            algorithm=algorithm,
            _config=KnotConfig(id="train"),
        )
        evaluated = Evaluator(
            model=trained,
            split=split,
            metrics=metric_tuple,
            _config=KnotConfig(id="evaluate"),
        )
        serialized = ModelSerializer(
            model=trained,
            _config=KnotConfig(id="serialize"),
        )
        registered = ModelRegistrar(
            serialized=serialized,
            model=trained,
            lineage=lineage,
            store=store,
            _config=KnotConfig(id="register"),
        )
        features = _holdout_features(
            split=split,
            _config=KnotConfig(id="holdout-features"),
        )
        Predictor(
            model_id=registered,
            features=features,
            lineage=lineage,
            store=store,
            _config=KnotConfig(id="predict"),
        )
        return _combine_continuous_training(
            model_id=registered,
            eval_report=evaluated,
            _config=KnotConfig(id="combine"),
        )
