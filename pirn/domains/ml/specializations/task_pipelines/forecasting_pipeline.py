"""``ForecastingPipeline`` — end-to-end time-series forecasting
SubTapestry: data load → split → train → evaluate via
:class:`TimeSeriesEvalPipeline`.
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


class ForecastingPipeline(SubTapestry):
    """End-to-end forecasting SubTapestry."""

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
                "ForecastingPipeline: pool must be a DatabaseConnectionPool"
            )
        if not isinstance(query, str) or not query:
            raise ValueError(
                "ForecastingPipeline: query must be a non-empty string"
            )
        if not isinstance(time_column, str) or not time_column:
            raise ValueError(
                "ForecastingPipeline: time_column must be a non-empty string"
            )
        if not isinstance(target_column, str) or not target_column:
            raise ValueError(
                "ForecastingPipeline: target_column must be a non-empty string"
            )
        feature_tuple = tuple(feature_names)
        if not feature_tuple:
            raise ValueError(
                "ForecastingPipeline: feature_names must be non-empty"
            )
        if not isinstance(horizon, int):
            raise TypeError("ForecastingPipeline: horizon must be an int")
        if horizon < 1:
            raise ValueError("ForecastingPipeline: horizon must be >= 1")
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError(
                "ForecastingPipeline: algorithm must be a non-empty string"
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
        with Tapestry() as inner:
            dataset = DatasetLoader(
                name="forecasting",
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
