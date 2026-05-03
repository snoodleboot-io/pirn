"""``RandomSearchTuner`` — random hyperparameter search.

Samples N random hyperparameter combinations from the search space,
trains and evaluates each, returns the best params + score wrapped in
a :class:`TrainedModel` / :class:`EvalReport` pair.
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


class RandomSearchTuner(SubTapestry):
    """Wrap :class:`HyperparamSearch` with random strategy."""

    def __init__(
        self,
        *,
        split: Knot,
        algorithm: str,
        search_space: Mapping[str, Sequence[Any]],
        primary_metric: str,
        n_trials: int = 20,
        random_seed: int = 42,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(split, Knot):
            raise TypeError("RandomSearchTuner: split must be a Knot")
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError(
                "RandomSearchTuner: algorithm must be a non-empty string"
            )
        if not isinstance(search_space, Mapping) or not search_space:
            raise ValueError(
                "RandomSearchTuner: search_space must be a non-empty Mapping"
            )
        if not isinstance(primary_metric, str) or not primary_metric:
            raise ValueError(
                "RandomSearchTuner: primary_metric must be a non-empty string"
            )
        if not isinstance(n_trials, int):
            raise TypeError("RandomSearchTuner: n_trials must be an int")
        if n_trials < 1:
            raise ValueError("RandomSearchTuner: n_trials must be >= 1")
        if not isinstance(random_seed, int):
            raise TypeError("RandomSearchTuner: random_seed must be an int")
        self._algorithm = algorithm
        self._search_space = {k: tuple(v) for k, v in search_space.items()}
        self._primary_metric = primary_metric
        self._n_trials = n_trials
        self._random_seed = random_seed
        super().__init__(split=split, _config=_config, **kwargs)

    async def process(
        self, split: DataSplit, **_: Any
    ) -> dict[str, Any]:
        """Sample N random hyperparameter combinations and return the best model and its evaluation.

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
                strategy="random",
                n_trials=self._n_trials,
                random_seed=self._random_seed,
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
                "RandomSearchTuner: search did not return a TrainedModel"
            )
        if not isinstance(report, EvalReport):
            raise TypeError(
                "RandomSearchTuner: evaluator did not return an EvalReport"
            )
        return {"best_model": model, "eval_report": report}
