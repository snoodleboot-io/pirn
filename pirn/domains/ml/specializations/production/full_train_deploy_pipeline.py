"""``FullTrainDeployPipeline`` — end-to-end SubTapestry: data load,
train/test split, train, evaluate, serialise, register, predict on a
holdout slice.

The pipeline returns a primitive summary mapping carrying the registered
``model_id`` and the produced :class:`EvalReport` so downstream
orchestration can hash the result without descending into knot-bearing
intermediates.

Algorithm:
    1. Receive ``pool``, ``query``, ``name``, ``feature_names``,
       ``target_name``, ``algorithm``, ``lineage``, ``store``, and
       ``metrics`` via process().
    2. Validate all inputs.
    3. Wire DatasetLoader → TrainTestSplit → Trainer → Evaluator →
       ModelSerializer → ModelRegistrar → Predictor in an inner Tapestry.
    4. Run via _run_inner() and return model_id and eval_report.


References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
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
        row: dict[str, Any] = {feature: float(index) for feature in split.test.feature_names}
        rows.append(row)
    return rows


class FullTrainDeployPipeline(SubTapestry):
    """End-to-end train + deploy SubTapestry."""

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
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        pool: DatabaseConnectionPool = None,
        query: str = "",
        name: str = "",
        feature_names: Sequence[str] = (),
        target_name: str = "",
        algorithm: str = "",
        lineage: LineageStore | None = None,
        store: ObjectStore = None,
        metrics: Sequence[str] = (),
        **_: Any,
    ) -> Mapping[str, Any]:
        """Load data, split, train, evaluate, serialise, and register the model; return a summary mapping with model_id and eval report.

        Args:
            pool: DatabaseConnectionPool for loading the dataset.
            query: Non-empty SQL query string.
            name: Non-empty dataset name.
            feature_names: Non-empty sequence of feature column names.
            target_name: Non-empty target column name.
            algorithm: Non-empty algorithm identifier.
            lineage: LineageStore for model registration.
            store: ObjectStore for model artifact storage.
            metrics: Non-empty sequence of metric names.

        Returns:
            Mapping with ``model_id`` (str registered in the object store) and
            ``eval_report`` (:class:`EvalReport` from the evaluation stage).

        Raises:
            ValueError: If any string param is empty or sequences are empty.
            TypeError: If pool, lineage, or store are the wrong types.
        """
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError("FullTrainDeployPipeline: pool must be a DatabaseConnectionPool")
        if not isinstance(query, str) or not query:
            raise ValueError("FullTrainDeployPipeline: query must be a non-empty string")
        if not isinstance(name, str) or not name:
            raise ValueError("FullTrainDeployPipeline: name must be a non-empty string")
        feature_tuple = tuple(feature_names)
        if not feature_tuple:
            raise ValueError("FullTrainDeployPipeline: feature_names must be non-empty")
        if not isinstance(target_name, str) or not target_name:
            raise ValueError("FullTrainDeployPipeline: target_name must be a non-empty string")
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError("FullTrainDeployPipeline: algorithm must be a non-empty string")
        if not isinstance(lineage, LineageStore):
            raise TypeError("FullTrainDeployPipeline: lineage must be a LineageStore")
        if not isinstance(store, ObjectStore):
            raise TypeError("FullTrainDeployPipeline: store must be an ObjectStore")
        metric_tuple = tuple(metrics)
        if not metric_tuple:
            raise ValueError("FullTrainDeployPipeline: metrics must be non-empty")
        with Tapestry() as inner:
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
            Evaluator(
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
        inner_result = await self._run_inner(inner)
        report: EvalReport = inner_result.outputs["evaluate"]
        return {
            "model_id": inner_result.outputs["register"],
            "eval_report": report,
        }
