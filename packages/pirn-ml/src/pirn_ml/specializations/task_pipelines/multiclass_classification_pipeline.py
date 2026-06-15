"""``MulticlassClassificationPipeline`` — end-to-end multiclass
classification SubTapestry. Uses macro-averaged variants of the canonical
classification metrics so the report is meaningful across more than two
target classes.

Algorithm:
    1. Receive ``pool``, ``query``, ``target_column``, ``feature_names``,
       ``n_classes``, and ``algorithm`` via process().
    2. Validate all inputs.
    3. Wire DatasetLoader → TrainTestSplit → Scaler → Trainer → Evaluator
       in an inner Tapestry.
    4. Run via _run_inner() and return the EvalMetadata.

Math:
    Softmax output for K classes:
        p(y=k | x) = exp(w_k^T x) / sum_{j=1}^{K} exp(w_j^T x)

    Macro-averaged F1 over K classes:
        F1_macro = (1/K) * sum_{k=1}^{K} 2*P_k*R_k / (P_k + R_k)

References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_ml.data_prep.dataset_loader import DatasetLoader
from pirn_ml.data_prep.train_test_split import TrainTestSplit
from pirn_ml.evaluation.evaluator import Evaluator
from pirn_ml.features.scaler import Scaler
from pirn_ml.training.trainer import Trainer


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
        pool: Knot | DatabaseConnectionPool,
        query: Knot | str,
        target_column: Knot | str,
        feature_names: Knot | Sequence[str],
        n_classes: Knot | int,
        algorithm: Knot | str = "logistic",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            pool=pool,
            query=query,
            target_column=target_column,
            feature_names=feature_names,
            n_classes=n_classes,
            algorithm=algorithm,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        pool: DatabaseConnectionPool | None = None,
        query: str = "",
        target_column: str = "",
        feature_names: Sequence[str] = (),
        n_classes: int = 3,
        algorithm: str = "logistic",
        **_: Any,
    ) -> Any:
        """Load data, split, scale, train a multiclass classifier, and return the macro-averaged EvalMetadata.

        Args:
            pool: DatabaseConnectionPool for loading the dataset.
            query: Non-empty SQL query string.
            target_column: Non-empty name of the target column.
            feature_names: Non-empty sequence of feature column names.
            n_classes: Number of classes; must be int >= 3.
            algorithm: Non-empty algorithm identifier.

        Returns:
            EvalReportPayload containing accuracy, precision_macro, recall_macro,
            f1_macro, and confusion_matrix metrics from the evaluation stage.

        Raises:
            ValueError: If any input fails validation.
            TypeError: If pool is not a DatabaseConnectionPool or n_classes is not int.
        """
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError(
                "MulticlassClassificationPipeline: pool must be a DatabaseConnectionPool"
            )
        if not isinstance(query, str) or not query:
            raise ValueError("MulticlassClassificationPipeline: query must be a non-empty string")
        if not isinstance(target_column, str) or not target_column:
            raise ValueError(
                "MulticlassClassificationPipeline: target_column must be a non-empty string"
            )
        feature_tuple = tuple(feature_names)
        if not feature_tuple:
            raise ValueError("MulticlassClassificationPipeline: feature_names must be non-empty")
        if not isinstance(n_classes, int):
            raise TypeError("MulticlassClassificationPipeline: n_classes must be an int")
        if n_classes < 3:
            raise ValueError(
                "MulticlassClassificationPipeline: n_classes must be >= 3 "
                "(use BinaryClassificationPipeline for binary tasks)"
            )
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError(
                "MulticlassClassificationPipeline: algorithm must be a non-empty string"
            )
        dataset = DatasetLoader(
            name="multiclass-classification",
            feature_names=feature_tuple,
            target_name=target_column,
            pool=pool,
            query=query,
            _config=KnotConfig(id="load"),
        )
        split = TrainTestSplit(
            dataset=dataset,
            _config=KnotConfig(id="split"),
        )
        preprocessed = Scaler(
            split=split,
            columns=feature_tuple,
            method="standardise",
            _config=KnotConfig(id="preprocess"),
        )
        trained = Trainer(
            split=preprocessed,
            algorithm=algorithm,
            hyperparameters={"n_classes": n_classes},
            _config=KnotConfig(id="train"),
        )
        return Evaluator(
            model=trained,
            split=preprocessed,
            metrics=self._multiclass_metrics,
            _config=KnotConfig(id="evaluate"),
        )
