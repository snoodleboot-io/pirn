"""``BaggingEnsembleBuilder`` — train N models on bootstrap samples and
aggregate predictions.

Classification uses majority voting; regression uses averaging. Returns
the ensemble :class:`ModelManifest` reference and its evaluation report.

Algorithm:
    1. Receive ``split``, ``algorithm``, ``n_estimators``, ``task``,
       ``metrics``, and ``hyperparameters`` via process().
    2. Validate all inputs.
    3. Wire N Trainer knots + EnsembleBuilder + Evaluator in an inner Tapestry.
    4. Run via _run_inner() and return ensemble model and eval report.

Math:
    Bootstrap sampling: each base model trains on n_bootstrap samples drawn with
    replacement from the training set of size n, where n_bootstrap = n by default.

    Classification (majority voting):
        y_hat = argmax_c sum_{i=1}^{N} I(y_hat_i == c)

    Regression (averaging):
        y_hat = (1/N) * sum_{i=1}^{N} y_hat_i

References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.domains.ml.evaluation.evaluator import Evaluator
from pirn.domains.ml.training.ensemble_builder import EnsembleBuilder
from pirn.domains.ml.training.trainer import Trainer
from pirn.domains.ml.types.eval_report_payload import EvalReportPayload
from pirn.domains.ml.types.model_manifest import ModelManifest
from pirn.domains.ml.types.split_manifest import SplitManifest
from pirn.nodes.sub_tapestry import SubTapestry


@knot
async def _emit_value(value: Any) -> Any:
    return value


@knot
async def _combine_ensemble_eval(
    ensemble_model: ModelManifest,
    eval_report: EvalReportPayload,
    n_estimators: int,
) -> dict[str, Any]:
    return {
        "ensemble_model": ensemble_model,
        "eval_report": eval_report,
        "n_estimators": n_estimators,
    }


class BaggingEnsembleBuilder(SubTapestry):
    """Train N base models on bootstrap samples and combine via voting/averaging."""

    valid_tasks: ClassVar[frozenset[str]] = frozenset({"classification", "regression"})

    def __init__(
        self,
        *,
        split: Knot,
        algorithm: Knot | str,
        n_estimators: Knot | int = 10,
        task: Knot | str = "classification",
        metrics: Knot | Sequence[str],
        hyperparameters: Knot | Mapping[str, Any] | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            split=split,
            algorithm=algorithm,
            n_estimators=n_estimators,
            task=task,
            metrics=metrics,
            hyperparameters=hyperparameters,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        split: SplitManifest,
        algorithm: str = "",
        n_estimators: int = 10,
        task: str = "classification",
        metrics: Sequence[str] = (),
        hyperparameters: Mapping[str, Any] | None = None,
        **_: Any,
    ) -> Any:
        """Train N base models, build a bagging ensemble, and return the ensemble model and its evaluation.

        Args:
            split: SplitManifest used for base model training and ensemble evaluation.
            algorithm: Non-empty algorithm identifier for base models.
            n_estimators: Number of base models; must be an int >= 2.
            task: Task type; must be one of {"classification", "regression"}.
            metrics: Non-empty sequence of metric names.
            hyperparameters: Optional mapping of hyperparameters.

        Returns:
            Dict with ``ensemble_model`` (ModelManifest), ``eval_report`` (EvalMetadata),
            and ``n_estimators`` (int).

        Raises:
            ValueError: If any input fails validation.
            TypeError: If base models or the ensemble do not return the expected types.
        """
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError("BaggingEnsembleBuilder: algorithm must be a non-empty string")
        if not isinstance(n_estimators, int):
            raise TypeError("BaggingEnsembleBuilder: n_estimators must be an int")
        if n_estimators < 2:
            raise ValueError("BaggingEnsembleBuilder: n_estimators must be >= 2")
        if task not in self.valid_tasks:
            raise ValueError(
                f"BaggingEnsembleBuilder: task must be one of {sorted(self.valid_tasks)}"
            )
        metric_tuple = tuple(metrics)
        if not metric_tuple:
            raise ValueError("BaggingEnsembleBuilder: metrics must be non-empty")
        for metric in metric_tuple:
            if not isinstance(metric, str) or not metric:
                raise ValueError(
                    "BaggingEnsembleBuilder: every metric name must be a non-empty string"
                )
        if hyperparameters is not None and not isinstance(hyperparameters, Mapping):
            raise TypeError("BaggingEnsembleBuilder: hyperparameters must be a Mapping")
        hp = dict(hyperparameters) if hyperparameters is not None else {}
        strategy = "voting" if task == "classification" else "blending"
        split_node = _emit_value(value=split, _config=KnotConfig(id="split"))
        base_models = []
        for i in range(n_estimators):
            model = Trainer(
                split=split_node,
                algorithm=algorithm,
                hyperparameters={**hp, "bootstrap_sample": i},
                _config=KnotConfig(id=f"train_{i}"),
            )
            base_models.append(model)
        ensemble = EnsembleBuilder(
            models=base_models,
            strategy=strategy,
            _config=KnotConfig(id="ensemble"),
        )
        evaluated = Evaluator(
            model=ensemble,
            split=split_node,
            metrics=metric_tuple,
            _config=KnotConfig(id="evaluate"),
        )
        n_est_node = _emit_value(value=n_estimators, _config=KnotConfig(id="n_estimators"))
        return _combine_ensemble_eval(
            ensemble_model=ensemble,
            eval_report=evaluated,
            n_estimators=n_est_node,
            _config=KnotConfig(id="combine"),
        )
