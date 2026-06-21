"""``BaselineEstablisher`` — train a simple baseline algorithm and record
its :class:`EvalMetadata` so subsequent experiments can be compared
against a documented starting point.

Composition (Block 5: ``data_prep`` (split is supplied) →
``training.Trainer`` → ``evaluation.Evaluator``):

1. :class:`Trainer` fits the baseline algorithm (default: ``"linear"``)
   with empty hyperparameters.
2. :class:`Evaluator` scores the trained model on ``split.test``.
3. The :class:`EvalMetadata` is returned as the baseline reference.

Algorithm:
    1. Receive ``split`` (SplitManifest), ``algorithm`` (str), and
       ``metrics`` (Sequence[str]) via process().
    2. Validate algorithm and metrics.
    3. Wire Trainer + Evaluator in an inner Tapestry.
    4. Run via _run_inner() and return the EvalMetadata.


References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_ml.evaluation.evaluator import Evaluator
from pirn_ml.training.trainer import Trainer
from pirn_ml.types.split_manifest import SplitManifest


@knot
async def _emit_value(value: Any) -> Any:
    return value


class BaselineEstablisher(SubTapestry):
    """Train a baseline algorithm and emit its :class:`EvalMetadata`."""

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
        split: SplitManifest,
        algorithm: str = "linear",
        metrics: Sequence[str] = ("accuracy",),
        **_: Any,
    ) -> Any:
        """Train the baseline algorithm on the split and return the evaluated EvalMetadata as a reference point.

        Args:
            split: SplitManifest used for training and evaluating the baseline.
            algorithm: Non-empty algorithm name string.
            metrics: Non-empty sequence of metric name strings.

        Returns:
            EvalReportPayload produced by the inner evaluator for the baseline model.

        Raises:
            ValueError: If algorithm or metrics are invalid.
            TypeError: If the inner evaluator does not return an EvalMetadata.
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
        split_node = _emit_value(value=split, _config=KnotConfig(id="split"))
        model = Trainer(
            split=split_node,
            algorithm=algorithm,
            _config=KnotConfig(id="train"),
        )
        return Evaluator(
            model=model,
            split=split_node,
            metrics=metric_tuple,
            _config=KnotConfig(id="evaluate"),
        )
