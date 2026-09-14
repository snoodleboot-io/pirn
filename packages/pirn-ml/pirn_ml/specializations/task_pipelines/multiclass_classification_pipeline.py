"""``MulticlassClassificationPipeline`` — end-to-end multiclass
classification SubTapestry. Uses macro-averaged variants of the canonical
classification metrics so the report is meaningful across more than two
target classes.

Algorithm:
    1. Receive ``pool``, ``query``, ``target_column``, ``feature_names``,
       ``n_classes``, and ``algorithm`` via process().
    2. Validate all inputs.
    3. Wire DatasetLoader → TrainTestSplit → Scaler → Trainer → Evaluator
       in an inner Tapestry (shared graph-building lives in
       :class:`~pirn_ml.specializations.task_pipelines.supervised_task_pipeline.SupervisedTaskPipeline`).
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
from typing import Any, ClassVar

from pirn.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_ml.specializations.task_pipelines.supervised_task_pipeline import (
    SupervisedTaskPipeline,
)


class MulticlassClassificationPipeline(SupervisedTaskPipeline):
    """End-to-end multiclass classification SubTapestry."""

    _dataset_name: ClassVar[str] = "multiclass-classification"
    _metrics: ClassVar[tuple[str, ...]] = (
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
        pool = self._require_pool("MulticlassClassificationPipeline", pool)
        query = self._require_query("MulticlassClassificationPipeline", query)
        target_column = self._require_target_column(
            "MulticlassClassificationPipeline", target_column
        )
        feature_tuple = self._require_feature_names(
            "MulticlassClassificationPipeline", feature_names
        )
        if not isinstance(n_classes, int):
            raise TypeError("MulticlassClassificationPipeline: n_classes must be an int")
        if n_classes < 3:
            raise ValueError(
                "MulticlassClassificationPipeline: n_classes must be >= 3 "
                "(use BinaryClassificationPipeline for binary tasks)"
            )
        algorithm = self._require_algorithm("MulticlassClassificationPipeline", algorithm)
        return self._build_evaluator(
            pool=pool,
            query=query,
            feature_tuple=feature_tuple,
            target_name=target_column,
            algorithm=algorithm,
            hyperparameters={"n_classes": n_classes},
        )
