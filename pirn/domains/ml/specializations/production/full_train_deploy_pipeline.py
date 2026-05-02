"""``FullTrainDeployPipeline`` — end-to-end SubTapestry: data load,
train/test split, train, evaluate, serialise, register, predict on a
holdout slice.

The pipeline returns a primitive summary mapping carrying the registered
``model_id`` and the produced :class:`EvalReport` so downstream
orchestration can hash the result without descending into knot-bearing
intermediates.
"""

from __future__ import annotations

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
    # Emit one placeholder feature row per holdout test row so the
    # downstream :class:`Predictor` has something to score. The orchestration
    # layer never materialises actual data here; concrete subclasses replace
    # this with a real feature loader.
    rows = []
    for index in range(int(split.test.row_count)):
        row: dict[str, Any] = {
            feature: float(index) for feature in split.test.feature_names
        }
        rows.append(row)
    return rows


class FullTrainDeployPipeline(SubTapestry):
    """End-to-end train + deploy SubTapestry."""

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
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError(
                "FullTrainDeployPipeline: pool must be a DatabaseConnectionPool"
            )
        if not isinstance(query, str) or not query:
            raise ValueError(
                "FullTrainDeployPipeline: query must be a non-empty string"
            )
        if not isinstance(name, str) or not name:
            raise ValueError(
                "FullTrainDeployPipeline: name must be a non-empty string"
            )
        feature_tuple = tuple(feature_names)
        if not feature_tuple:
            raise ValueError(
                "FullTrainDeployPipeline: feature_names must be non-empty"
            )
        if not isinstance(target_name, str) or not target_name:
            raise ValueError(
                "FullTrainDeployPipeline: target_name must be a non-empty string"
            )
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError(
                "FullTrainDeployPipeline: algorithm must be a non-empty string"
            )
        if not isinstance(lineage, LineageStore):
            raise TypeError(
                "FullTrainDeployPipeline: lineage must be a LineageStore"
            )
        if not isinstance(store, ObjectStore):
            raise TypeError(
                "FullTrainDeployPipeline: store must be an ObjectStore"
            )
        metric_tuple = tuple(metrics)
        if not metric_tuple:
            raise ValueError(
                "FullTrainDeployPipeline: metrics must be non-empty"
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
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> Mapping[str, Any]:
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
        }
