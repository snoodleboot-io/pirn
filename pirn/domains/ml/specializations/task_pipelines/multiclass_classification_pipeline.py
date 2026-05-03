"""``MulticlassClassificationPipeline`` — end-to-end multiclass
classification SubTapestry. Uses macro-averaged variants of the canonical
classification metrics so the report is meaningful across more than two
target classes.
"""

from __future__ import annotations

from typing import Any, Sequence

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.domains.ml.data_prep.dataset_loader import DatasetLoader
from pirn.domains.ml.data_prep.train_test_split import TrainTestSplit
from pirn.domains.ml.evaluation.evaluator import Evaluator
from pirn.domains.ml.features.scaler import Scaler
from pirn.domains.ml.training.trainer import Trainer
from pirn.domains.ml.types.eval_report import EvalReport
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class MulticlassClassificationPipeline(SubTapestry):
    """End-to-end multiclass classification SubTapestry."""

    _multiclass_metrics: tuple[str, ...] = (
        "accuracy",
        "precision_macro",
        "recall_macro",
        "f1_macro",
        "confusion_matrix",
    )

    def __init__(
        self,
        *,
        pool: DatabaseConnectionPool,
        query: str,
        target_column: str,
        feature_names: Sequence[str],
        n_classes: int,
        algorithm: str = "logistic",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError(
                "MulticlassClassificationPipeline: pool must be a DatabaseConnectionPool"
            )
        if not isinstance(query, str) or not query:
            raise ValueError(
                "MulticlassClassificationPipeline: query must be a non-empty string"
            )
        if not isinstance(target_column, str) or not target_column:
            raise ValueError(
                "MulticlassClassificationPipeline: target_column must be a "
                "non-empty string"
            )
        feature_tuple = tuple(feature_names)
        if not feature_tuple:
            raise ValueError(
                "MulticlassClassificationPipeline: feature_names must be non-empty"
            )
        if not isinstance(n_classes, int):
            raise TypeError(
                "MulticlassClassificationPipeline: n_classes must be an int"
            )
        if n_classes < 3:
            raise ValueError(
                "MulticlassClassificationPipeline: n_classes must be >= 3 "
                "(use BinaryClassificationPipeline for binary tasks)"
            )
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError(
                "MulticlassClassificationPipeline: algorithm must be a non-empty string"
            )
        self._pool = pool
        self._query = query
        self._target_column = target_column
        self._feature_names = feature_tuple
        self._n_classes = n_classes
        self._algorithm = algorithm
        super().__init__(_config=_config, **kwargs)

    @property
    def n_classes(self) -> int:
        return self._n_classes

    async def process(self, **_: Any) -> EvalReport:
        """Load data, split, scale, train a multiclass classifier, and return the macro-averaged EvalReport.

        Returns:
            EvalReport containing accuracy, precision_macro, recall_macro,
            f1_macro, and confusion_matrix metrics from the evaluation stage.
        """
        with Tapestry() as inner:
            dataset = DatasetLoader(
                name="multiclass-classification",
                feature_names=self._feature_names,
                target_name=self._target_column,
                pool=self._pool,
                query=self._query,
                _config=KnotConfig(id="load"),
            )
            split = TrainTestSplit(
                dataset=dataset,
                _config=KnotConfig(id="split"),
            )
            preprocessed = Scaler(
                split=split,
                columns=self._feature_names,
                method="standardise",
                _config=KnotConfig(id="preprocess"),
            )
            trained = Trainer(
                split=preprocessed,
                algorithm=self._algorithm,
                hyperparameters={"n_classes": self._n_classes},
                _config=KnotConfig(id="train"),
            )
            Evaluator(
                model=trained,
                split=preprocessed,
                metrics=self._multiclass_metrics,
                _config=KnotConfig(id="evaluate"),
            )
        inner_result = await self._run_inner(inner)
        return inner_result.outputs["evaluate"]
