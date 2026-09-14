"""``TimeSeriesEvalPipeline`` — SubTapestry for forecasting evaluation.

Computes MAPE, sMAPE, and MASE for a time-series forecasting model.
The ``time_column`` is recorded on the report's ``details`` section so
downstream consumers can group / window the report appropriately.

Algorithm:
    1. Receive ``model`` (ModelManifest), ``split`` (SplitManifest), and
       ``time_column`` (str) via process().
    2. Validate time_column is a non-empty string.
    3. Wire an inner Tapestry with Evaluator using forecasting metrics
       (shared with the other ``*_eval_pipeline`` SubTapestries via
       :class:`~pirn_ml.specializations.evaluation.eval_pipeline_base.EvalPipelineBase`).
    4. Run the inner Tapestry via _run_inner() and decorate the EvalMetadata
       with time_column in its details mapping.


References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import KnotFactory
from pirn.core.parameter import Parameter

from pirn_ml.specializations.evaluation.eval_pipeline_base import EvalPipelineBase
from pirn_ml.types.eval_metadata import EvalMetadata
from pirn_ml.types.eval_metrics import EvalMetrics
from pirn_ml.types.eval_report_payload import EvalReportPayload
from pirn_ml.types.model_manifest import ModelManifest
from pirn_ml.types.split_manifest import SplitManifest


@KnotFactory.knot
async def _decorate_time_column(
    report: EvalReportPayload,
    time_column: str,
) -> EvalReportPayload:
    decorated_details: dict[str, Any] = dict(report.data.details)
    decorated_details["time_column"] = time_column
    return EvalReportPayload(
        metadata=EvalMetadata(
            model_id=report.metadata.model_id,
            dataset_name=report.metadata.dataset_name,
            evaluated_at=report.metadata.evaluated_at,
        ),
        data=EvalMetrics(
            scores=report.data.scores,
            details=MappingProxyType(decorated_details),
        ),
    )


class TimeSeriesEvalPipeline(EvalPipelineBase):
    """Evaluate a forecasting model with MAPE, sMAPE, and MASE."""

    _metrics: ClassVar[tuple[str, ...]] = ("mape", "smape", "mase")

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
        model: ModelManifest,
        split: SplitManifest,
        time_column: str = "",
        **_: Any,
    ) -> Any:
        """Evaluate the forecasting model with MAPE, sMAPE, and MASE and return an EvalReportPayload decorated with the time column.

        Args:
            model: ModelManifest reference to evaluate.
            split: SplitManifest whose test partition is used for scoring.
            time_column: Non-empty name of the time column in the dataset.

        Returns:
            EvalReportPayload containing mape, smape, and mase metrics, with time_column in details.

        Raises:
            ValueError: If time_column is empty.
        """
        if not isinstance(time_column, str) or not time_column:
            raise ValueError("TimeSeriesEvalPipeline: time_column must be a non-empty string")
        model_node, split_node = self._wire_model_split(model, split)
        evaluated = self._evaluate(model_node, split_node, self._metrics)
        time_col_node = Parameter(
            "time_column", str, default=time_column, _config=KnotConfig(id="time_column")
        )
        return _decorate_time_column(
            report=evaluated,
            time_column=time_col_node,
            _config=KnotConfig(id="decorate"),
        )
