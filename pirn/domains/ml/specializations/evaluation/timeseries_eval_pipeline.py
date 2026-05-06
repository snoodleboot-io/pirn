"""``TimeSeriesEvalPipeline`` — SubTapestry for forecasting evaluation.

Computes MAPE, sMAPE, and MASE for a time-series forecasting model.
The ``time_column`` is recorded on the report's ``details`` section so
downstream consumers can group / window the report appropriately.

Algorithm:
    1. Receive ``model`` (TrainedModel), ``split`` (DataSplit), and
       ``time_column`` (str) via process().
    2. Validate time_column is a non-empty string.
    3. Wire an inner Tapestry with Evaluator using forecasting metrics.
    4. Run the inner Tapestry via _run_inner() and decorate the EvalReport
       with time_column in its details mapping.


References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.domains.ml.evaluation.evaluator import Evaluator
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.eval_report import EvalReport
from pirn.domains.ml.types.trained_model import TrainedModel
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


@knot
async def _emit_value(value: Any) -> Any:
    return value


class TimeSeriesEvalPipeline(SubTapestry):
    """Evaluate a forecasting model with MAPE, sMAPE, and MASE."""

    _forecasting_metrics: tuple[str, ...] = ("mape", "smape", "mase")

    def __init__(
        self,
        *,
        model: Knot,
        split: Knot,
        time_column: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            model=model,
            split=split,
            time_column=time_column,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        model: TrainedModel,
        split: DataSplit,
        time_column: str = "",
        **_: Any,
    ) -> EvalReport:
        """Evaluate the forecasting model with MAPE, sMAPE, and MASE and return an EvalReport decorated with the time column.

        Args:
            model: TrainedModel reference to evaluate.
            split: DataSplit whose test partition is used for scoring.
            time_column: Non-empty name of the time column in the dataset.

        Returns:
            EvalReport containing mape, smape, and mase metrics, with time_column in details.

        Raises:
            ValueError: If time_column is empty.
        """
        if not isinstance(time_column, str) or not time_column:
            raise ValueError(
                "TimeSeriesEvalPipeline: time_column must be a non-empty string"
            )
        with Tapestry() as inner:
            model_node = _emit_value(
                value=model, _config=KnotConfig(id="model")
            )
            split_node = _emit_value(
                value=split, _config=KnotConfig(id="split")
            )
            Evaluator(
                model=model_node,
                split=split_node,
                metrics=self._forecasting_metrics,
                _config=KnotConfig(id="evaluate"),
            )
        inner_result = await self._run_inner(inner)
        report: EvalReport = inner_result.outputs["evaluate"]
        decorated_details: dict[str, Any] = dict(report.details)
        decorated_details["time_column"] = time_column
        return EvalReport(
            model_id=report.model_id,
            dataset_name=report.dataset_name,
            metrics=report.metrics,
            details=MappingProxyType(decorated_details),
            evaluated_at=report.evaluated_at,
        )
