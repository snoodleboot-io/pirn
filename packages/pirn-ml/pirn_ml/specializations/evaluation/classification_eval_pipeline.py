"""``ClassificationEvalPipeline`` — SubTapestry that evaluates a model
on a held-out split with the canonical classification metric set.

Composition:

1. The configured ``model`` and ``split`` parents are forwarded into the
   inner tapestry as proxy emitters so the inner :class:`Evaluator`
   reads them as upstream knots (shared with the other
   ``*_eval_pipeline`` SubTapestries via
   :class:`~pirn_ml.specializations.evaluation._eval_pipeline_base._EvalPipelineBase`).
2. :class:`Evaluator` computes the classification metrics
   (accuracy, precision, recall, F1, ROC-AUC, confusion matrix).

The output is the :class:`EvalMetadata` produced by the inner evaluator.

Algorithm:
    1. Receive ``model`` (ModelManifest) and ``split`` (SplitManifest) via process().
    2. Wire an inner Tapestry with Evaluator using the canonical classification metrics.
    3. Run the inner Tapestry via _run_inner() and return the EvalMetadata.


References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_ml.specializations.evaluation._eval_pipeline_base import _EvalPipelineBase
from pirn_ml.types.model_manifest import ModelManifest
from pirn_ml.types.split_manifest import SplitManifest


class ClassificationEvalPipeline(_EvalPipelineBase):
    """Evaluate a classifier with the canonical classification metric set."""

    _metrics: ClassVar[tuple[str, ...]] = (
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

    async def process(self, model: ModelManifest, split: SplitManifest, **_: Any) -> Any:
        """Evaluate the model using the canonical classification metric set and return the resulting EvalMetadata.

        Args:
            model: ModelManifest reference to evaluate.
            split: SplitManifest whose test partition is used for scoring.

        Returns:
            EvalReportPayload containing accuracy, precision, recall, f1, roc_auc, and confusion_matrix.
        """
        model_node, split_node = self._wire_model_split(model, split)
        return self._evaluate(model_node, split_node, self._metrics)
