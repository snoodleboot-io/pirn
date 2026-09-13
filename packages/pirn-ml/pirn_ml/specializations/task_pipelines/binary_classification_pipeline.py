"""``BinaryClassificationPipeline`` — end-to-end binary classification
SubTapestry: data load → train/test split → preprocess (scaling) → train
→ evaluate.

The output is the :class:`EvalMetadata` produced by the final evaluation
stage so callers can gate downstream knots on the model's score.

Algorithm:
    1. Receive ``pool``, ``query``, ``target_column``, ``feature_names``,
       and ``algorithm`` via process().
    2. Validate all inputs.
    3. Wire DatasetLoader → TrainTestSplit → Scaler → Trainer → Evaluator
       in an inner Tapestry (shared graph-building lives in
       :class:`~pirn_ml.specializations.task_pipelines._supervised_task_pipeline._SupervisedTaskPipeline`).
    4. Run via _run_inner() and return the EvalMetadata.

Math:
    Binary cross-entropy loss:
        L = -(1/n) * sum_i [y_i * log(p_i) + (1 - y_i) * log(1 - p_i)]

    Sigmoid output: p_i = 1 / (1 + exp(-w^T x_i))

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

from pirn_ml.specializations.task_pipelines._supervised_task_pipeline import (
    _SupervisedTaskPipeline,
)


class BinaryClassificationPipeline(_SupervisedTaskPipeline):
    """End-to-end binary classification SubTapestry."""

    _dataset_name: ClassVar[str] = "binary-classification"
    _metrics: ClassVar[tuple[str, ...]] = (
        "accuracy",
        "precision",
        "recall",
        "f1",
        "roc_auc",
    )

    def __init__(
        self,
        *,
        pool: Knot | DatabaseConnectionPool,
        query: Knot | str,
        target_column: Knot | str,
        feature_names: Knot | Sequence[str],
        algorithm: Knot | str = "logistic",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            pool=pool,
            query=query,
            target_column=target_column,
            feature_names=feature_names,
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
        algorithm: str = "logistic",
        **_: Any,
    ) -> Any:
        """Load data, split, scale, train a binary classifier, and return the EvalMetadata from the evaluation stage.

        Args:
            pool: DatabaseConnectionPool for loading the dataset.
            query: Non-empty SQL query string.
            target_column: Non-empty name of the target column.
            feature_names: Non-empty sequence of feature column names.
            algorithm: Non-empty algorithm identifier.

        Returns:
            EvalReportPayload containing accuracy, precision, recall, f1, and
            roc_auc metrics from the evaluation stage.

        Raises:
            ValueError: If any input fails validation.
            TypeError: If pool is not a DatabaseConnectionPool.
        """
        pool = self._require_pool("BinaryClassificationPipeline", pool)
        query = self._require_query("BinaryClassificationPipeline", query)
        target_column = self._require_target_column("BinaryClassificationPipeline", target_column)
        feature_tuple = self._require_feature_names("BinaryClassificationPipeline", feature_names)
        algorithm = self._require_algorithm("BinaryClassificationPipeline", algorithm)
        return self._build_evaluator(
            pool=pool,
            query=query,
            feature_tuple=feature_tuple,
            target_name=target_column,
            algorithm=algorithm,
        )
