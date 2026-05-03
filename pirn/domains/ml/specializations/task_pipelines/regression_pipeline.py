"""``RegressionPipeline`` — end-to-end regression SubTapestry: data load
→ split → preprocess → train → evaluate. The default algorithm is
``random_forest`` because tree ensembles are the most robust default for
mixed-feature tabular regression tasks.
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


class RegressionPipeline(SubTapestry):
    """End-to-end regression SubTapestry."""

    _regression_metrics: tuple[str, ...] = ("rmse", "mae", "r2", "mape")

    def __init__(
        self,
        *,
        pool: DatabaseConnectionPool,
        query: str,
        target_column: str,
        feature_names: Sequence[str],
        algorithm: str = "random_forest",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError(
                "RegressionPipeline: pool must be a DatabaseConnectionPool"
            )
        if not isinstance(query, str) or not query:
            raise ValueError(
                "RegressionPipeline: query must be a non-empty string"
            )
        if not isinstance(target_column, str) or not target_column:
            raise ValueError(
                "RegressionPipeline: target_column must be a non-empty string"
            )
        feature_tuple = tuple(feature_names)
        if not feature_tuple:
            raise ValueError(
                "RegressionPipeline: feature_names must be non-empty"
            )
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError(
                "RegressionPipeline: algorithm must be a non-empty string"
            )
        self._pool = pool
        self._query = query
        self._target_column = target_column
        self._feature_names = feature_tuple
        self._algorithm = algorithm
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> EvalReport:
        """Load data, split, scale, train a regressor, and return the RMSE/MAE/R2/MAPE EvalReport.

        Returns:
            EvalReport containing rmse, mae, r2, and mape metrics from the
            regression evaluation stage.
        """
        with Tapestry() as inner:
            dataset = DatasetLoader(
                name="regression",
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
