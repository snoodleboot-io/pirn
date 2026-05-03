"""``RegressionEvalPipeline`` — SubTapestry for canonical regression
evaluation: RMSE, MAE, R-squared, MAPE.
"""

from __future__ import annotations

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


class RegressionEvalPipeline(SubTapestry):
    """Evaluate a regressor with RMSE, MAE, R-squared, and MAPE."""

    _regression_metrics: tuple[str, ...] = (
        "rmse",
        "mae",
        "r2",
        "mape",
    )

    def __init__(
        self,
        *,
        model: Knot,
        split: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(model, Knot):
            raise TypeError("RegressionEvalPipeline: model must be a Knot")
        if not isinstance(split, Knot):
            raise TypeError("RegressionEvalPipeline: split must be a Knot")
        super().__init__(model=model, split=split, _config=_config, **kwargs)

    async def process(
        self, model: TrainedModel, split: DataSplit, **_: Any
    ) -> EvalReport:
        """Evaluate the regressor with RMSE, MAE, R-squared, and MAPE and return the resulting EvalReport.

        Args:
            model: TrainedModel reference to evaluate.
            split: DataSplit whose test partition is used for scoring.

        Returns:
            EvalReport containing rmse, mae, r2, and mape metrics.
        """
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
                metrics=self._regression_metrics,
                _config=KnotConfig(id="evaluate"),
            )
        inner_result = await self._run_inner(inner)
        return inner_result.outputs["evaluate"]
