"""``_SupervisedTaskPipeline`` — shared tabular supervised-task graph.

Five ``task_pipelines`` SubTapestries (``BinaryClassificationPipeline``,
``MulticlassClassificationPipeline``, ``RegressionPipeline``,
``AnomalyDetectionPipeline``, ``ActiveLearningLoop``) wire the identical
skeleton over a ``DatabaseConnectionPool`` query result: load a dataset,
split it, optionally scale the feature columns, train, and evaluate. They
differ only in the dataset name, the metric set, whether a ``Scaler``
stage is inserted, and family-specific constructor parameters and
validation (``n_classes`` for multiclass, ``contamination`` for anomaly
detection, ``n_rounds``/``query_size`` for active learning). This base
class centralises the shared wiring; each subclass keeps its own
``__init__`` (constructor signatures are part of the public API and stay
unchanged) and its own ``process()`` validation order, calling
:meth:`_build_evaluator` once its inputs are validated.

Algorithm:
    1. A subclass's ``process()`` validates its own inputs (common checks
       delegated to the ``_require_*`` static helpers here; family-specific
       checks such as ``n_classes`` or ``contamination`` stay inline).
    2. It calls :meth:`_build_evaluator` with the resolved pool, query,
       feature tuple, target name (or ``None``), algorithm, and any extra
       hyperparameters.
    3. :meth:`_build_evaluator` wires ``DatasetLoader`` (named by the
       subclass's ``_dataset_name``) -> ``TrainTestSplit`` -> ``Scaler``
       (only when ``_use_scaler`` is ``True``) -> ``Trainer`` ->
       ``Evaluator`` (scored on the subclass's ``_metrics``) in the inner
       Tapestry, using the same knot ids every subclass used before this
       refactor (``load``, ``split``, ``preprocess``, ``train``,
       ``evaluate``).
    4. Returns the terminal ``Evaluator`` knot; the base ``SubTapestry``
       runs the inner tapestry.

References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, ClassVar

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_ml.data_prep.dataset_loader import DatasetLoader
from pirn_ml.data_prep.train_test_split import TrainTestSplit
from pirn_ml.evaluation.evaluator import Evaluator
from pirn_ml.features.scaler import Scaler
from pirn_ml.training.trainer import Trainer


class _SupervisedTaskPipeline(SubTapestry):
    """Shared DatasetLoader -> TrainTestSplit -> [Scaler] -> Trainer -> Evaluator graph."""

    _dataset_name: ClassVar[str] = ""
    _metrics: ClassVar[tuple[str, ...]] = ()
    _use_scaler: ClassVar[bool] = True

    @staticmethod
    def _require_pool(cls_name: str, pool: Any) -> DatabaseConnectionPool:
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError(f"{cls_name}: pool must be a DatabaseConnectionPool")
        return pool

    @staticmethod
    def _require_query(cls_name: str, query: Any) -> str:
        if not isinstance(query, str) or not query:
            raise ValueError(f"{cls_name}: query must be a non-empty string")
        return query

    @staticmethod
    def _require_target_column(cls_name: str, target_column: Any) -> str:
        if not isinstance(target_column, str) or not target_column:
            raise ValueError(f"{cls_name}: target_column must be a non-empty string")
        return target_column

    @staticmethod
    def _require_feature_names(cls_name: str, feature_names: Sequence[str]) -> tuple[str, ...]:
        feature_tuple = tuple(feature_names)
        if not feature_tuple:
            raise ValueError(f"{cls_name}: feature_names must be non-empty")
        return feature_tuple

    @staticmethod
    def _require_algorithm(cls_name: str, algorithm: Any) -> str:
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError(f"{cls_name}: algorithm must be a non-empty string")
        return algorithm

    def _build_evaluator(
        self,
        *,
        pool: DatabaseConnectionPool,
        query: str,
        feature_tuple: tuple[str, ...],
        target_name: str | None,
        algorithm: str,
        hyperparameters: Mapping[str, Any] | None = None,
    ) -> Knot:
        dataset = DatasetLoader(
            name=self._dataset_name,
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
        prepared: Knot = split
        if self._use_scaler:
            prepared = Scaler(
                split=split,
                columns=feature_tuple,
                method="standardise",
                _config=KnotConfig(id="preprocess"),
            )
        trained = Trainer(
            split=prepared,
            algorithm=algorithm,
            hyperparameters=dict(hyperparameters) if hyperparameters is not None else {},
            _config=KnotConfig(id="train"),
        )
        return Evaluator(
            model=trained,
            split=prepared,
            metrics=self._metrics,
            _config=KnotConfig(id="evaluate"),
        )
