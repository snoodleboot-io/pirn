"""``BayesianSearchTuner`` — Bayesian hyperparameter search.

Wraps :class:`HyperparamSearch` with ``strategy="bayesian"``. The number
of evaluated trials is capped by ``n_trials``; the orchestration layer's
search returns a deterministic best candidate so the pipeline is
well-defined offline. Concrete subclasses of :class:`HyperparamSearch`
override scoring to drive a real BO loop.

Algorithm:
    1. Receive ``split`` (DataSplit), ``algorithm``, ``search_space``,
       ``primary_metric``, and ``n_trials`` via process().
    2. Validate all inputs.
    3. Wire HyperparamSearch (bayesian) + Evaluator in an inner Tapestry.
    4. Run via _run_inner() and return best_model and eval_report.


References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.domains.ml.evaluation.evaluator import Evaluator
from pirn.domains.ml.training.hyperparam_search import HyperparamSearch
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.eval_report import EvalReport
from pirn.domains.ml.types.trained_model import TrainedModel
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


@knot
async def _emit_value(value: Any) -> Any:
    return value


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
        split: DataSplit,
        algorithm: str = "",
        search_space: Mapping[str, Sequence[Any]] | None = None,
        primary_metric: str = "",
        n_trials: int = 50,
        **_: Any,
    ) -> dict[str, Any]:
        """Run a Bayesian hyperparameter search for up to n_trials and return the best model and its evaluation report.

        Args:
            split: DataSplit used for candidate training and evaluation.
            algorithm: Non-empty algorithm name string.
            search_space: Non-empty mapping of hyperparameter name to candidate values.
            primary_metric: Non-empty metric name to report.
            n_trials: Maximum number of trials; must be an int >= 1.

        Returns:
            Dict with ``best_model`` (TrainedModel) and ``eval_report`` (EvalReport).

        Raises:
            ValueError: If any input fails validation.
            TypeError: If the inner search or evaluator returns an unexpected type.
        """
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError(
                "BayesianSearchTuner: algorithm must be a non-empty string"
            )
        ss = search_space or {}
        if not isinstance(ss, Mapping) or not ss:
            raise ValueError(
                "BayesianSearchTuner: search_space must be a non-empty Mapping"
            )
        if not isinstance(primary_metric, str) or not primary_metric:
            raise ValueError(
                "BayesianSearchTuner: primary_metric must be a non-empty string"
            )
        if not isinstance(n_trials, int):
            raise TypeError("BayesianSearchTuner: n_trials must be an int")
        if n_trials < 1:
            raise ValueError("BayesianSearchTuner: n_trials must be >= 1")
        frozen_space = {k: tuple(v) for k, v in ss.items()}
        with Tapestry() as inner:
            split_node = _emit_value(
                value=split, _config=KnotConfig(id="split")
            )
            best = HyperparamSearch(
                split=split_node,
                algorithm=algorithm,
                search_space=frozen_space,
                strategy="bayesian",
                n_trials=n_trials,
                _config=KnotConfig(id="search"),
            )
            Evaluator(
                model=best,
                split=split_node,
                metrics=(primary_metric,),
                _config=KnotConfig(id="evaluate"),
            )
        result = await self._run_inner(inner)
        model = result.outputs["search"]
        report = result.outputs["evaluate"]
        if not isinstance(model, TrainedModel):
            raise TypeError(
                "BayesianSearchTuner: search did not return a TrainedModel"
            )
        if not isinstance(report, EvalReport):
            raise TypeError(
                "BayesianSearchTuner: evaluator did not return an EvalReport"
            )
        return {"best_model": model, "eval_report": report}
