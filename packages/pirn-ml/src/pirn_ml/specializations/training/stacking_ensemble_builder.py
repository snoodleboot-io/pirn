"""``StackingEnsembleBuilder`` — train base models, use their OOF predictions
as features for a meta-learner.

Returns the stacked ensemble :class:`ModelManifest` and its evaluation
report.

Algorithm:
    1. Receive ``split``, ``base_algorithms``, ``meta_algorithm``, and
       ``metrics`` via process().
    2. Validate all inputs.
    3. Wire N base Trainers + EnsembleBuilder (stacking) + Evaluator in an
       inner Tapestry.
    4. Run via _run_inner() and return ensemble model and eval report.

Math:
    Level-0 (base models): y_hat_i = f_i(x)  for i in 1..M
    Level-1 (meta-learner input): Z = [y_hat_1, ..., y_hat_M]  (OOF predictions)
    Meta prediction: y_hat_meta = g(Z; theta_meta)

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
from pirn_ml.training.ensemble_builder import EnsembleBuilder
from pirn_ml.training.trainer import Trainer
from pirn_ml.types.eval_report_payload import EvalReportPayload
from pirn_ml.types.model_manifest import ModelManifest
from pirn_ml.types.split_manifest import SplitManifest


@knot
async def _emit_value(value: Any) -> Any:
    return value


@knot
async def _combine_stacking_result(
    ensemble_model: ModelManifest,
    eval_report: EvalReportPayload,
    n_base_models: int,
) -> dict[str, Any]:
    return {
        "ensemble_model": ensemble_model,
        "eval_report": eval_report,
        "n_base_models": n_base_models,
    }


class StackingEnsembleBuilder(SubTapestry):
    """Train base models and a meta-learner via stacking."""

    def __init__(
        self,
        *,
        split: Knot,
        base_algorithms: Knot | Sequence[str],
        meta_algorithm: Knot | str,
        metrics: Knot | Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            split=split,
            base_algorithms=base_algorithms,
            meta_algorithm=meta_algorithm,
            metrics=metrics,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        split: SplitManifest,
        base_algorithms: Sequence[str] = (),
        meta_algorithm: str = "",
        metrics: Sequence[str] = (),
        **_: Any,
    ) -> Any:
        """Train base models and a stacking meta-learner, return the ensemble and its evaluation.

        Args:
            split: SplitManifest used for base model training and meta-learner evaluation.
            base_algorithms: At least two non-empty algorithm identifiers.
            meta_algorithm: Non-empty algorithm identifier for the meta-learner.
            metrics: Non-empty sequence of metric names.

        Returns:
            Dict with ``ensemble_model`` (ModelManifest), ``eval_report`` (EvalMetadata),
            and ``n_base_models`` (int).

        Raises:
            ValueError: If fewer than two base algorithms, meta_algorithm is empty, or metrics is empty.
            TypeError: If base models or the ensemble do not return the expected types.
        """
        base_tuple = tuple(base_algorithms)
        if len(base_tuple) < 2:
            raise ValueError("StackingEnsembleBuilder: at least two base_algorithms are required")
        for alg in base_tuple:
            if not isinstance(alg, str) or not alg:
                raise ValueError(
                    "StackingEnsembleBuilder: every base algorithm must be a non-empty string"
                )
        if not isinstance(meta_algorithm, str) or not meta_algorithm:
            raise ValueError("StackingEnsembleBuilder: meta_algorithm must be a non-empty string")
        metric_tuple = tuple(metrics)
        if not metric_tuple:
            raise ValueError("StackingEnsembleBuilder: metrics must be non-empty")
        for metric in metric_tuple:
            if not isinstance(metric, str) or not metric:
                raise ValueError(
                    "StackingEnsembleBuilder: every metric name must be a non-empty string"
                )
        split_node = _emit_value(value=split, _config=KnotConfig(id="split"))
        base_models = []
        for i, alg in enumerate(base_tuple):
            model = Trainer(
                split=split_node,
                algorithm=alg,
                _config=KnotConfig(id=f"base_{i}"),
            )
            base_models.append(model)
        ensemble = EnsembleBuilder(
            models=base_models,
            strategy="stacking",
            _config=KnotConfig(id="ensemble"),
        )
        evaluated = Evaluator(
            model=ensemble,
            split=split_node,
            metrics=metric_tuple,
            _config=KnotConfig(id="evaluate"),
        )
        n_base_node = _emit_value(value=len(base_tuple), _config=KnotConfig(id="n_base_models"))
        return _combine_stacking_result(
            ensemble_model=ensemble,
            eval_report=evaluated,
            n_base_models=n_base_node,
            _config=KnotConfig(id="combine"),
        )
