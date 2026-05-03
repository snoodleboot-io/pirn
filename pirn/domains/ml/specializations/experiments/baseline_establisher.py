"""``BaselineEstablisher`` — train a simple baseline algorithm and record
its :class:`EvalReport` so subsequent experiments can be compared
against a documented starting point.

Composition (Block 5: ``data_prep`` (split is supplied) →
``training.Trainer`` → ``evaluation.Evaluator``):

1. :class:`Trainer` fits the baseline algorithm (default: ``"linear"``)
   with empty hyperparameters.
2. :class:`Evaluator` scores the trained model on ``split.test``.
3. The :class:`EvalReport` is returned as the baseline reference.
"""

from __future__ import annotations

from typing import Any, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.domains.ml.evaluation.evaluator import Evaluator
from pirn.domains.ml.training.trainer import Trainer
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.eval_report import EvalReport
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


@knot
async def _emit_value(value: Any) -> Any:
    return value


class BaselineEstablisher(SubTapestry):
    """Train a baseline algorithm and emit its :class:`EvalReport`."""

    def __init__(
        self,
        *,
        split: Knot,
        algorithm: str = "linear",
        metrics: Sequence[str] = ("accuracy",),
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(split, Knot):
            raise TypeError(
                "BaselineEstablisher: split must be a Knot"
            )
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError(
                "BaselineEstablisher: algorithm must be a non-empty string"
            )
        metric_tuple = tuple(metrics)
        if not metric_tuple:
            raise ValueError(
                "BaselineEstablisher: metrics must be non-empty"
            )
        for metric in metric_tuple:
            if not isinstance(metric, str) or not metric:
                raise ValueError(
                    "BaselineEstablisher: every metric name must be a "
                    "non-empty string"
                )
        self._algorithm = algorithm
        self._metrics = metric_tuple
        super().__init__(split=split, _config=_config, **kwargs)

    async def process(self, split: DataSplit, **_: Any) -> EvalReport:
        """Train the baseline algorithm on the split and return the evaluated EvalReport as a reference point.

        Args:
            split: DataSplit used for training and evaluating the baseline.

        Returns:
            EvalReport produced by the inner evaluator for the baseline model.

        Raises:
            TypeError: If the inner evaluator does not return an EvalReport.
        """
        with Tapestry() as inner:
            split_node = _emit_value(
                value=split, _config=KnotConfig(id="split")
            )
            model = Trainer(
                split=split_node,
                algorithm=self._algorithm,
                _config=KnotConfig(id="train"),
            )
            Evaluator(
                model=model,
                split=split_node,
                metrics=self._metrics,
                _config=KnotConfig(id="evaluate"),
            )
        inner_result = await self._run_inner(inner)
        report = inner_result.outputs["evaluate"]
        if not isinstance(report, EvalReport):
            raise TypeError(
                "BaselineEstablisher: inner evaluator did not return an "
                "EvalReport"
            )
        return report
