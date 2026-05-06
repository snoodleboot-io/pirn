"""``TimeSeriesForecastingPipeline`` — end-to-end time-series pipeline:
feature engineering → train/val split → model train → forecast → evaluation.

Algorithm:
    1. Receive ``pool``, ``query``, ``time_column``, ``target_column``,
       ``feature_names``, ``horizon``, and ``algorithm`` via process().
    2. Validate all inputs.
    3. Wire DatasetLoader → TrainTestSplit → Trainer → TimeSeriesEvalPipeline
       in an inner Tapestry.
    4. Run via _run_inner() and return the EvalReport.


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
        pool: Knot | DatabaseConnectionPool,
        query: Knot | str,
        time_column: Knot | str,
        target_column: Knot | str,
        feature_names: Knot | Sequence[str],
        horizon: Knot | int = 7,
        algorithm: Knot | str = "arima",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            pool=pool,
            query=query,
            time_column=time_column,
            target_column=target_column,
            feature_names=feature_names,
            horizon=horizon,
            algorithm=algorithm,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        pool: DatabaseConnectionPool = None,
        query: str = "",
        time_column: str = "",
        target_column: str = "",
        feature_names: Sequence[str] = (),
        horizon: int = 7,
        algorithm: str = "arima",
        **_: Any,
    ) -> EvalReport:
        """Run the full time-series pipeline: load → split → train → evaluate with temporal metrics.

        Args:
            pool: DatabaseConnectionPool for loading the dataset.
            query: Non-empty SQL query string.
            time_column: Non-empty name of the time column.
            target_column: Non-empty name of the target column.
            feature_names: Non-empty sequence of feature column names.
            horizon: Forecast horizon; must be int >= 1.
            algorithm: Non-empty algorithm identifier.

        Returns:
            EvalReport containing mape, smape, and mase metrics from the evaluation stage.

        Raises:
            ValueError: If any input fails validation.
            TypeError: If pool is not a DatabaseConnectionPool.
        """
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
        with Tapestry() as inner:
            dataset = DatasetLoader(
                name="ts-forecasting",
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
            trained = Trainer(
                split=split,
                algorithm=algorithm,
                hyperparameters={"horizon": horizon},
                _config=KnotConfig(id="train"),
            )
            TimeSeriesEvalPipeline(
                model=trained,
                split=split,
                time_column=time_column,
                _config=KnotConfig(id="evaluate"),
            )
        inner_result = await self._run_inner(inner)
        return inner_result.outputs["evaluate"]
