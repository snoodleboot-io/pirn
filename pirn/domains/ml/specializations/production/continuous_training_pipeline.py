"""``ContinuousTrainingPipeline`` — scheduled re-training SubTapestry.

Same composition as :class:`FullTrainDeployPipeline` but designed to be
re-run on a cadence. Before retraining the pipeline performs a freshness
check against the configured :class:`LineageStore`: if the last training
event is younger than ``freshness_window_days`` the pipeline short-circuits
and returns the cached model id without retraining.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Sequence

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
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.eval_report import EvalReport
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


@knot
async def _holdout_features(split: DataSplit) -> list[Mapping[str, Any]]:
    rows = []
    for index in range(int(split.test.row_count)):
        row: dict[str, Any] = {
            feature: float(index) for feature in split.test.feature_names
        }
        rows.append(row)
    return rows


class ContinuousTrainingPipeline(SubTapestry):
    """Scheduled retraining SubTapestry with a freshness gate."""

    def __init__(
        self,
        *,
        pool: DatabaseConnectionPool,
        query: str,
        name: str,
        feature_names: Sequence[str],
        target_name: str,
        algorithm: str,
        lineage: LineageStore,
        store: ObjectStore,
        metrics: Sequence[str],
        freshness_window_days: int = 1,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError(
                "ContinuousTrainingPipeline: pool must be a DatabaseConnectionPool"
            )
        if not isinstance(query, str) or not query:
            raise ValueError(
                "ContinuousTrainingPipeline: query must be a non-empty string"
            )
        if not isinstance(name, str) or not name:
            raise ValueError(
                "ContinuousTrainingPipeline: name must be a non-empty string"
            )
        feature_tuple = tuple(feature_names)
        if not feature_tuple:
            raise ValueError(
                "ContinuousTrainingPipeline: feature_names must be non-empty"
            )
        if not isinstance(target_name, str) or not target_name:
            raise ValueError(
                "ContinuousTrainingPipeline: target_name must be a non-empty string"
            )
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError(
                "ContinuousTrainingPipeline: algorithm must be a non-empty string"
            )
        if not isinstance(lineage, LineageStore):
            raise TypeError(
                "ContinuousTrainingPipeline: lineage must be a LineageStore"
            )
        if not isinstance(store, ObjectStore):
            raise TypeError(
                "ContinuousTrainingPipeline: store must be an ObjectStore"
            )
        metric_tuple = tuple(metrics)
        if not metric_tuple:
            raise ValueError(
                "ContinuousTrainingPipeline: metrics must be non-empty"
            )
        if not isinstance(freshness_window_days, int):
            raise TypeError(
                "ContinuousTrainingPipeline: freshness_window_days must be an int"
            )
        if freshness_window_days < 0:
            raise ValueError(
                "ContinuousTrainingPipeline: freshness_window_days must be >= 0"
            )
        self._pool = pool
        self._query = query
        self._name = name
        self._feature_names = feature_tuple
        self._target_name = target_name
        self._algorithm = algorithm
        self._lineage = lineage
        self._store = store
        self._metrics = metric_tuple
        self._freshness_window_days = freshness_window_days
        super().__init__(_config=_config, **kwargs)

    @property
    def freshness_window_days(self) -> int:
        return self._freshness_window_days

    async def _is_fresh(self) -> tuple[bool, str | None]:
        try:
            lineage_record = await self._lineage.fetch_lineage(self._name)
        except Exception:
            return False, None
        events = lineage_record.get("events") if isinstance(
            lineage_record, Mapping
        ) else None
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
        now = datetime.now(timezone.utc)
        if recorded.tzinfo is None:
            recorded = recorded.replace(tzinfo=timezone.utc)
        if now - recorded < timedelta(days=self._freshness_window_days):
            return True, last_model_id
        return False, None

    async def process(self, **_: Any) -> Mapping[str, Any]:
        """Check freshness against the lineage store and, if stale, retrain and deploy the model; return a summary with the model_id and eval report.

        Returns:
            Mapping with ``model_id`` (str), ``eval_report``
            (:class:`EvalReport` or ``None`` if skipped), and ``skipped``
            (bool indicating whether retraining was bypassed due to freshness).
        """
        is_fresh, cached_model_id = await self._is_fresh()
        if is_fresh and cached_model_id is not None:
            return {
                "model_id": cached_model_id,
                "eval_report": None,
                "skipped": True,
            }
        with Tapestry() as inner:
            dataset = DatasetLoader(
                name=self._name,
                feature_names=self._feature_names,
                target_name=self._target_name,
                pool=self._pool,
                query=self._query,
                _config=KnotConfig(id="load"),
            )
            split = TrainTestSplit(
                dataset=dataset,
                _config=KnotConfig(id="split"),
            )
            trained = Trainer(
                split=split,
                algorithm=self._algorithm,
                _config=KnotConfig(id="train"),
            )
            Evaluator(
                model=trained,
                split=split,
                metrics=self._metrics,
                _config=KnotConfig(id="evaluate"),
            )
            serialized = ModelSerializer(
                model=trained,
                _config=KnotConfig(id="serialize"),
            )
            registered = ModelRegistrar(
                serialized=serialized,
                model=trained,
                lineage=self._lineage,
                store=self._store,
                _config=KnotConfig(id="register"),
            )
            features = _holdout_features(
                split=split,
                _config=KnotConfig(id="holdout-features"),
            )
            Predictor(
                model_id=registered,
                features=features,
                lineage=self._lineage,
                store=self._store,
                _config=KnotConfig(id="predict"),
            )
        inner_result = await self._run_inner(inner)
        report: EvalReport = inner_result.outputs["evaluate"]
        return {
            "model_id": inner_result.outputs["register"],
            "eval_report": report,
            "skipped": False,
        }
