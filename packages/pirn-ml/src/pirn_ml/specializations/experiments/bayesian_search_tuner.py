"""``BayesianSearchTuner`` — Bayesian hyperparameter search.

Wraps :class:`HyperparamSearch` with ``strategy="bayesian"``. The number
of evaluated trials is capped by ``n_trials``; the orchestration layer's
search returns a deterministic best candidate so the pipeline is
well-defined offline. Concrete subclasses of :class:`HyperparamSearch`
override scoring to drive a real BO loop.

Algorithm:
    1. Receive ``split`` (SplitManifest), ``algorithm``, ``search_space``,
       ``primary_metric``, and ``n_trials`` via process().
    2. Validate all inputs.
    3. Wire HyperparamSearch (bayesian) + Evaluator in an inner Tapestry.
    4. Run via _run_inner() and return best_model and eval_report.

Math:
    Gaussian Process surrogate: f(theta) ~ GP(mu(theta), k(theta, theta'))
    Acquisition function (Expected Improvement):
        EI(theta) = E[max(0, f(theta) - f*)]  where f* is the current best.

    Best config: theta* = argmax_{theta} EI(theta)  over n_trials evaluations.

References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_ml.evaluation.evaluator import Evaluator
from pirn_ml.training.hyperparam_search import HyperparamSearch
from pirn_ml.types.eval_report_payload import EvalReportPayload
from pirn_ml.types.model_manifest import ModelManifest
from pirn_ml.types.split_manifest import SplitManifest


@knot
async def _emit_value(value: Any) -> Any:
    return value


@knot
async def _combine_search_eval(
    best_model: ModelManifest,
    eval_report: EvalReportPayload,
) -> dict[str, Any]:
    return {"best_model": best_model, "eval_report": eval_report}


class BayesianSearchTuner(SubTapestry):
    """Wrap :class:`HyperparamSearch` with bayesian strategy."""

    def __init__(
        self,
        *,
        split: Knot,
        algorithm: Knot | str,
        search_space: Knot | Mapping[str, Sequence[Any]],
        primary_metric: Knot | str,
        n_trials: Knot | int = 50,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            split=split,
            algorithm=algorithm,
            search_space=search_space,
            primary_metric=primary_metric,
            n_trials=n_trials,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        split: SplitManifest,
        algorithm: str = "",
        search_space: Mapping[str, Sequence[Any]] | None = None,
        primary_metric: str = "",
        n_trials: int = 50,
        **_: Any,
    ) -> Any:
        """Run a Bayesian hyperparameter search for up to n_trials and return the best model and its evaluation report.

        Args:
            split: SplitManifest used for candidate training and evaluation.
            algorithm: Non-empty algorithm name string.
            search_space: Non-empty mapping of hyperparameter name to candidate values.
            primary_metric: Non-empty metric name to report.
            n_trials: Maximum number of trials; must be an int >= 1.

        Returns:
            Dict with ``best_model`` (ModelManifest) and ``eval_report`` (EvalMetadata).

        Raises:
            ValueError: If any input fails validation.
            TypeError: If the inner search or evaluator returns an unexpected type.
        """
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError("BayesianSearchTuner: algorithm must be a non-empty string")
        ss = search_space or {}
        if not isinstance(ss, Mapping) or not ss:
            raise ValueError("BayesianSearchTuner: search_space must be a non-empty Mapping")
        if not isinstance(primary_metric, str) or not primary_metric:
            raise ValueError("BayesianSearchTuner: primary_metric must be a non-empty string")
        if not isinstance(n_trials, int):
            raise TypeError("BayesianSearchTuner: n_trials must be an int")
        if n_trials < 1:
            raise ValueError("BayesianSearchTuner: n_trials must be >= 1")
        frozen_space = {k: tuple(v) for k, v in ss.items()}
        split_node = _emit_value(value=split, _config=KnotConfig(id="split"))
        best = HyperparamSearch(
            split=split_node,
            algorithm=algorithm,
            search_space=frozen_space,
            strategy="bayesian",
            n_trials=n_trials,
            _config=KnotConfig(id="search"),
        )
        evaluated = Evaluator(
            model=best,
            split=split_node,
            metrics=(primary_metric,),
            _config=KnotConfig(id="evaluate"),
        )
        return _combine_search_eval(
            best_model=best,
            eval_report=evaluated,
            _config=KnotConfig(id="combine"),
        )
