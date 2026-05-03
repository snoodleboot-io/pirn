"""``TimeSeriesForecastingPipeline`` — end-to-end time-series pipeline:
feature engineering → train/val split → model train → forecast → evaluation.
"""

from __future__ import annotations

from typing import Any, Sequence

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.domains.ml.data_prep.dataset_loader import DatasetLoader
from pirn.domains.ml.data_prep.train_test_split import TrainTestSplit
from pirn.domains.ml.specializations.evaluation.timeseries_eval_pipeline import (
    TimeSeriesEvalPipeline,
)
from pirn.domains.ml.training.trainer import Trainer
from pirn.domains.ml.types.eval_report import EvalReport
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


class TimeSeriesForecastingPipeline(SubTapestry):
    """End-to-end time-series forecasting pipeline with feature engineering and evaluation."""

    def __init__(
        self,
        *,
        pool: DatabaseConnectionPool,
        query: str,
        time_column: str,
        target_column: str,
        feature_names: Sequence[str],
        horizon: int = 7,
        algorithm: str = "arima",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError(
                "TimeSeriesForecastingPipeline: pool must be a DatabaseConnectionPool"
            )
        if not isinstance(query, str) or not query:
            raise ValueError(
                "TimeSeriesForecastingPipeline: query must be a non-empty string"
            )
        if not isinstance(time_column, str) or not time_column:
            raise ValueError(
                "TimeSeriesForecastingPipeline: time_column must be a non-empty string"
            )
        if not isinstance(target_column, str) or not target_column:
            raise ValueError(
                "TimeSeriesForecastingPipeline: target_column must be a non-empty string"
            )
        feature_tuple = tuple(feature_names)
        if not feature_tuple:
            raise ValueError(
                "TimeSeriesForecastingPipeline: feature_names must be non-empty"
            )
        if not isinstance(horizon, int) or horizon < 1:
            raise ValueError(
                "TimeSeriesForecastingPipeline: horizon must be an int >= 1"
            )
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError(
                "TimeSeriesForecastingPipeline: algorithm must be a non-empty string"
            )
        self._pool = pool
        self._query = query
        self._time_column = time_column
        self._target_column = target_column
        self._feature_names = feature_tuple
        self._horizon = horizon
        self._algorithm = algorithm
        super().__init__(_config=_config, **kwargs)

    @property
    def horizon(self) -> int:
        return self._horizon

    async def process(self, **_: Any) -> EvalReport:
        """Run the full time-series pipeline: load → split → train → evaluate with temporal metrics.

        Returns:
            EvalReport containing mape, smape, and mase metrics from the evaluation stage.
        """
        with Tapestry() as inner:
            dataset = DatasetLoader(
                name="ts-forecasting",
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
            trained = Trainer(
                split=split,
                algorithm=self._algorithm,
                hyperparameters={"horizon": self._horizon},
                _config=KnotConfig(id="train"),
            )
            TimeSeriesEvalPipeline(
                model=trained,
                split=split,
                time_column=self._time_column,
                _config=KnotConfig(id="evaluate"),
            )
        inner_result = await self._run_inner(inner)
        return inner_result.outputs["evaluate"]
