"""``ClassificationEvalPipeline`` — SubTapestry that evaluates a model
on a held-out split with the canonical classification metric set.

Composition:

1. The configured ``model`` and ``split`` parents are forwarded into the
   inner tapestry as proxy emitters so the inner :class:`Evaluator`
   reads them as upstream knots.
2. :class:`Evaluator` computes the classification metrics
   (accuracy, precision, recall, F1, ROC-AUC, confusion matrix).

The output is the :class:`EvalReport` produced by the inner evaluator.

Algorithm:
    1. Receive ``model`` (TrainedModel) and ``split`` (DataSplit) via process().
    2. Wire an inner Tapestry with Evaluator using the canonical classification metrics.
    3. Run the inner Tapestry via _run_inner() and return the EvalReport.


References:
    N/A — pirn-native implementation.
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


class ClassificationEvalPipeline(SubTapestry):
    """Evaluate a classifier with the canonical classification metric set."""

    _classification_metrics: tuple[str, ...] = (
        "accuracy",
        "precision",
        "recall",
        "f1",
        "roc_auc",
        "confusion_matrix",
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

    async def process(
        self, model: TrainedModel, split: DataSplit, **_: Any
    ) -> EvalReport:
        """Evaluate the model using the canonical classification metric set and return the resulting EvalReport.

        Args:
            model: TrainedModel reference to evaluate.
            split: DataSplit whose test partition is used for scoring.

        Returns:
            EvalReport containing accuracy, precision, recall, f1, roc_auc, and confusion_matrix.
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
                metrics=self._classification_metrics,
                _config=KnotConfig(id="evaluate"),
            )
        inner_result = await self._run_inner(inner)
        return inner_result.outputs["evaluate"]
