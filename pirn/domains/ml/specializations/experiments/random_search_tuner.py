"""``RandomSearchTuner`` — random hyperparameter search.

Samples N random hyperparameter combinations from the search space,
trains and evaluates each, returns the best params + score wrapped in
a :class:`TrainedModel` / :class:`EvalReport` pair.

Algorithm:
    1. Receive ``split`` (DataSplit), ``algorithm``, ``search_space``,
       ``primary_metric``, ``n_trials``, and ``random_seed`` via process().
    2. Validate all inputs.
    3. Wire HyperparamSearch (random) + Evaluator in an inner Tapestry.
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


class RandomSearchTuner(SubTapestry):
    """Wrap :class:`HyperparamSearch` with random strategy."""

    def __init__(
        self,
        *,
        split: Knot,
        algorithm: Knot | str,
        search_space: Knot | Mapping[str, Sequence[Any]],
        primary_metric: Knot | str,
        n_trials: Knot | int = 20,
        random_seed: Knot | int = 42,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            split=split,
            algorithm=algorithm,
            search_space=search_space,
            primary_metric=primary_metric,
            n_trials=n_trials,
            random_seed=random_seed,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        split: DataSplit,
        algorithm: str = "",
        search_space: Mapping[str, Sequence[Any]] | None = None,
        primary_metric: str = "",
        n_trials: int = 20,
        random_seed: int = 42,
        **_: Any,
    ) -> dict[str, Any]:
        """Sample N random hyperparameter combinations and return the best model and its evaluation.

        Args:
            split: DataSplit used for candidate training and evaluation.
            algorithm: Non-empty algorithm name string.
            search_space: Non-empty mapping of hyperparameter name to candidate values.
            primary_metric: Non-empty metric name to report.
            n_trials: Number of random trials; must be an int >= 1.
            random_seed: Seed for deterministic sampling.

        Returns:
            Dict with ``best_model`` (TrainedModel) and ``eval_report`` (EvalReport).

        Raises:
            ValueError: If any input fails validation.
            TypeError: If the inner search or evaluator returns an unexpected type.
        """
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError("RandomSearchTuner: algorithm must be a non-empty string")
        ss = search_space or {}
        if not isinstance(ss, Mapping) or not ss:
            raise ValueError("RandomSearchTuner: search_space must be a non-empty Mapping")
        if not isinstance(primary_metric, str) or not primary_metric:
            raise ValueError("RandomSearchTuner: primary_metric must be a non-empty string")
        if not isinstance(n_trials, int):
            raise TypeError("RandomSearchTuner: n_trials must be an int")
        if n_trials < 1:
            raise ValueError("RandomSearchTuner: n_trials must be >= 1")
        if not isinstance(random_seed, int):
            raise TypeError("RandomSearchTuner: random_seed must be an int")
        frozen_space = {k: tuple(v) for k, v in ss.items()}
        with Tapestry() as inner:
            split_node = _emit_value(value=split, _config=KnotConfig(id="split"))
            best = HyperparamSearch(
                split=split_node,
                algorithm=algorithm,
                search_space=frozen_space,
                strategy="random",
                n_trials=n_trials,
                random_seed=random_seed,
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
            raise TypeError("RandomSearchTuner: search did not return a TrainedModel")
        if not isinstance(report, EvalReport):
            raise TypeError("RandomSearchTuner: evaluator did not return an EvalReport")
        return {"best_model": model, "eval_report": report}
