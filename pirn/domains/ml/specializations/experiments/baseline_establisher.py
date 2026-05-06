"""``BaselineEstablisher`` — train a simple baseline algorithm and record
its :class:`EvalReport` so subsequent experiments can be compared
against a documented starting point.

Composition (Block 5: ``data_prep`` (split is supplied) →
``training.Trainer`` → ``evaluation.Evaluator``):

1. :class:`Trainer` fits the baseline algorithm (default: ``"linear"``)
   with empty hyperparameters.
2. :class:`Evaluator` scores the trained model on ``split.test``.
3. The :class:`EvalReport` is returned as the baseline reference.

Algorithm:
    1. Receive ``split`` (DataSplit), ``algorithm`` (str), and
       ``metrics`` (Sequence[str]) via process().
    2. Validate algorithm and metrics.
    3. Wire Trainer + Evaluator in an inner Tapestry.
    4. Run via _run_inner() and return the EvalReport.


References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

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
        algorithm: Knot | str = "linear",
        metrics: Knot | Sequence[str] = ("accuracy",),
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            split=split,
            algorithm=algorithm,
            metrics=metrics,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        split: DataSplit,
        algorithm: str = "linear",
        metrics: Sequence[str] = ("accuracy",),
        **_: Any,
    ) -> EvalReport:
        """Train the baseline algorithm on the split and return the evaluated EvalReport as a reference point.

        Args:
            split: DataSplit used for training and evaluating the baseline.
            algorithm: Non-empty algorithm name string.
            metrics: Non-empty sequence of metric name strings.

        Returns:
            EvalReport produced by the inner evaluator for the baseline model.

        Raises:
            ValueError: If algorithm or metrics are invalid.
            TypeError: If the inner evaluator does not return an EvalReport.
        """
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError("BaselineEstablisher: algorithm must be a non-empty string")
        metric_tuple = tuple(metrics)
        if not metric_tuple:
            raise ValueError("BaselineEstablisher: metrics must be non-empty")
        for metric in metric_tuple:
            if not isinstance(metric, str) or not metric:
                raise ValueError(
                    "BaselineEstablisher: every metric name must be a non-empty string"
                )
        with Tapestry() as inner:
            split_node = _emit_value(value=split, _config=KnotConfig(id="split"))
            model = Trainer(
                split=split_node,
                algorithm=algorithm,
                _config=KnotConfig(id="train"),
            )
            Evaluator(
                model=model,
                split=split_node,
                metrics=metric_tuple,
                _config=KnotConfig(id="evaluate"),
            )
        inner_result = await self._run_inner(inner)
        report = inner_result.outputs["evaluate"]
        if not isinstance(report, EvalReport):
            raise TypeError("BaselineEstablisher: inner evaluator did not return an EvalReport")
        return report
