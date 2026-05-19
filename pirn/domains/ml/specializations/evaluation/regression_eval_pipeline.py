"""``RegressionEvalPipeline`` — SubTapestry for canonical regression
evaluation: RMSE, MAE, R-squared, MAPE.

Algorithm:
    1. Receive ``model`` (ModelManifest) and ``split`` (SplitManifest) via process().
    2. Wire an inner Tapestry with Evaluator using the canonical regression metrics.
    3. Run the inner Tapestry via _run_inner() and return the EvalMetadata.


References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.domains.ml.evaluation.evaluator import Evaluator
from pirn.domains.ml.types.model_manifest import ModelManifest
from pirn.domains.ml.types.split_manifest import SplitManifest
from pirn.nodes.sub_tapestry import SubTapestry


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
        super().__init__(model=model, split=split, _config=_config, **kwargs)

    async def process(self, model: ModelManifest, split: SplitManifest, **_: Any) -> Any:
        """Evaluate the regressor with RMSE, MAE, R-squared, and MAPE and return the resulting EvalMetadata.

        Args:
            model: ModelManifest reference to evaluate.
            split: SplitManifest whose test partition is used for scoring.

        Returns:
            EvalReportPayload containing rmse, mae, r2, and mape metrics.
        """
        model_node = _emit_value(value=model, _config=KnotConfig(id="model"))
        split_node = _emit_value(value=split, _config=KnotConfig(id="split"))
        return Evaluator(
            model=model_node,
            split=split_node,
            metrics=self._regression_metrics,
            _config=KnotConfig(id="evaluate"),
        )
