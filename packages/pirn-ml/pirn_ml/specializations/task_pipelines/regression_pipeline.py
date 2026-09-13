"""``RegressionPipeline`` — end-to-end regression SubTapestry: data load
→ split → preprocess → train → evaluate. The default algorithm is
``random_forest`` because tree ensembles are the most robust default for
mixed-feature tabular regression tasks.

Algorithm:
    1. Receive ``pool``, ``query``, ``target_column``, ``feature_names``,
       and ``algorithm`` via process().
    2. Validate all inputs.
    3. Wire DatasetLoader → TrainTestSplit → Scaler → Trainer → Evaluator
       in an inner Tapestry (shared graph-building lives in
       :class:`~pirn_ml.specializations.task_pipelines._supervised_task_pipeline._SupervisedTaskPipeline`).
    4. Run via _run_inner() and return the EvalMetadata.

Math:
    MSE loss: L = (1/n) * sum_i (y_i - y_hat_i)^2
    RMSE = sqrt(MSE)
    MAE  = (1/n) * sum_i |y_i - y_hat_i|
    R^2  = 1 - sum_i(y_i - y_hat_i)^2 / sum_i(y_i - y_bar)^2

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


class RegressionPipeline(_SupervisedTaskPipeline):
    """End-to-end regression SubTapestry."""

    _dataset_name: ClassVar[str] = "regression"
    _metrics: ClassVar[tuple[str, ...]] = ("rmse", "mae", "r2", "mape")

    def __init__(
        self,
        *,
        pool: Knot | DatabaseConnectionPool,
        query: Knot | str,
        target_column: Knot | str,
        feature_names: Knot | Sequence[str],
        algorithm: Knot | str = "random_forest",
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
        algorithm: str = "random_forest",
        **_: Any,
    ) -> Any:
        """Load data, split, scale, train a regressor, and return the RMSE/MAE/R2/MAPE EvalMetadata.

        Args:
            pool: DatabaseConnectionPool for loading the dataset.
            query: Non-empty SQL query string.
            target_column: Non-empty name of the target column.
            feature_names: Non-empty sequence of feature column names.
            algorithm: Non-empty algorithm identifier.

        Returns:
            EvalReportPayload containing rmse, mae, r2, and mape metrics from the
            regression evaluation stage.

        Raises:
            ValueError: If any input fails validation.
            TypeError: If pool is not a DatabaseConnectionPool.
        """
        pool = self._require_pool("RegressionPipeline", pool)
        query = self._require_query("RegressionPipeline", query)
        target_column = self._require_target_column("RegressionPipeline", target_column)
        feature_tuple = self._require_feature_names("RegressionPipeline", feature_names)
        algorithm = self._require_algorithm("RegressionPipeline", algorithm)
        return self._build_evaluator(
            pool=pool,
            query=query,
            feature_tuple=feature_tuple,
            target_name=target_column,
            algorithm=algorithm,
        )
