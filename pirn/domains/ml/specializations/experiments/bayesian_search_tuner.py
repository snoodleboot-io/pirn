"""``BayesianSearchTuner`` — Bayesian hyperparameter search.

Wraps :class:`HyperparamSearch` with ``strategy="bayesian"``. The number
of evaluated trials is capped by ``n_trials``; the orchestration layer's
search returns a deterministic best candidate so the pipeline is
well-defined offline. Concrete subclasses of :class:`HyperparamSearch`
override scoring to drive a real BO loop.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

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
        algorithm: str,
        search_space: Mapping[str, Sequence[Any]],
        primary_metric: str,
        n_trials: int = 50,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(split, Knot):
            raise TypeError("BayesianSearchTuner: split must be a Knot")
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError(
                "BayesianSearchTuner: algorithm must be a non-empty string"
            )
        if not isinstance(search_space, Mapping) or not search_space:
            raise ValueError(
                "BayesianSearchTuner: search_space must be a non-empty "
                "Mapping"
            )
        if not isinstance(primary_metric, str) or not primary_metric:
            raise ValueError(
                "BayesianSearchTuner: primary_metric must be a non-empty "
                "string"
            )
        if not isinstance(n_trials, int):
            raise TypeError("BayesianSearchTuner: n_trials must be an int")
        if n_trials < 1:
            raise ValueError("BayesianSearchTuner: n_trials must be >= 1")
        self._algorithm = algorithm
        self._search_space = {k: tuple(v) for k, v in search_space.items()}
        self._primary_metric = primary_metric
        self._n_trials = n_trials
        super().__init__(split=split, _config=_config, **kwargs)

    @property
    def n_trials(self) -> int:
        return self._n_trials

    async def process(
        self, split: DataSplit, **_: Any
    ) -> dict[str, Any]:
        """Run a Bayesian hyperparameter search for up to n_trials and return the best model and its evaluation report.

        Args:
            split: DataSplit used for candidate training and evaluation.

        Returns:
            Dict with ``best_model`` (TrainedModel) and ``eval_report`` (EvalReport).

        Raises:
            TypeError: If the inner search or evaluator returns an unexpected type.
        """
        with Tapestry() as inner:
            split_node = _emit_value(
                value=split, _config=KnotConfig(id="split")
            )
            best = HyperparamSearch(
                split=split_node,
                algorithm=self._algorithm,
                search_space=self._search_space,
                strategy="bayesian",
                n_trials=self._n_trials,
                _config=KnotConfig(id="search"),
            )
            Evaluator(
                model=best,
                split=split_node,
                metrics=(self._primary_metric,),
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
