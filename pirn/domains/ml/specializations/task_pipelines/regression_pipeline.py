"""``RegressionPipeline`` — end-to-end regression SubTapestry: data load
→ split → preprocess → train → evaluate. The default algorithm is
``random_forest`` because tree ensembles are the most robust default for
mixed-feature tabular regression tasks.

Algorithm:
    1. Receive ``pool``, ``query``, ``target_column``, ``feature_names``,
       and ``algorithm`` via process().
    2. Validate all inputs.
    3. Wire DatasetLoader → TrainTestSplit → Scaler → Trainer → Evaluator
       in an inner Tapestry.
    4. Run via _run_inner() and return the EvalMetadata.


References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.domains.ml.data_prep.dataset_loader import DatasetLoader
from pirn.domains.ml.data_prep.train_test_split import TrainTestSplit
from pirn.domains.ml.evaluation.evaluator import Evaluator
from pirn.domains.ml.features.scaler import Scaler
from pirn.domains.ml.training.trainer import Trainer
from pirn.domains.ml.types.eval_report_payload import EvalReportPayload
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class RegressionPipeline(SubTapestry):
    """End-to-end regression SubTapestry."""

    _regression_metrics: tuple[str, ...] = ("rmse", "mae", "r2", "mape")

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
    ) -> EvalReportPayload:
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
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError("RegressionPipeline: pool must be a DatabaseConnectionPool")
        if not isinstance(query, str) or not query:
            raise ValueError("RegressionPipeline: query must be a non-empty string")
        if not isinstance(target_column, str) or not target_column:
            raise ValueError("RegressionPipeline: target_column must be a non-empty string")
        feature_tuple = tuple(feature_names)
        if not feature_tuple:
            raise ValueError("RegressionPipeline: feature_names must be non-empty")
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError("RegressionPipeline: algorithm must be a non-empty string")
        with Tapestry() as inner:
            dataset = DatasetLoader(
                name="regression",
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
                _config=KnotConfig(id="train"),
            )
            Evaluator(
                model=trained,
                split=preprocessed,
                metrics=self._regression_metrics,
                _config=KnotConfig(id="evaluate"),
            )
        inner_result = await self._run_inner(inner)
        return inner_result.outputs["evaluate"]
