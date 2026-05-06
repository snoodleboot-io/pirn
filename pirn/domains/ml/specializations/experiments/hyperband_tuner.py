"""``HyperbandTuner`` — successive-halving hyperparameter optimisation.

Trains many configurations for a few iterations, retains the top half,
and repeats until one configuration survives. Returns the best config
wrapped in a :class:`TrainedModel` / :class:`EvalReport` pair.

The orchestration layer implements successive halving over a randomly
sampled initial population using :class:`HyperparamSearch` with the
``random`` strategy. Concrete subclasses override scoring to perform
real partial-fit iterations.

Algorithm:
    1. Receive ``split`` (DataSplit), ``algorithm``, ``search_space``,
       ``primary_metric``, ``max_configs``, and ``random_seed`` via process().
    2. Validate all inputs.
    3. Compute n_trials from max_configs and log2 rounding.
    4. Wire HyperparamSearch (random) + Evaluator in an inner Tapestry.
    5. Run via _run_inner() and return best_model, eval_report, rounds.

Math:
    rounds = ceil(log2(max_configs))
    n_trials = max(1, max_configs // 2^(rounds - 1))

References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

import math
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


class HyperbandTuner(SubTapestry):
    """Successive-halving search using :class:`HyperparamSearch`."""

    def __init__(
        self,
        *,
        split: Knot,
        algorithm: Knot | str,
        search_space: Knot | Mapping[str, Sequence[Any]],
        primary_metric: Knot | str,
        max_configs: Knot | int = 16,
        random_seed: Knot | int = 42,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            split=split,
            algorithm=algorithm,
            search_space=search_space,
            primary_metric=primary_metric,
            max_configs=max_configs,
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
        max_configs: int = 16,
        random_seed: int = 42,
        **_: Any,
    ) -> dict[str, Any]:
        """Run successive-halving and return the surviving best model and its evaluation.

        Args:
            split: DataSplit used for candidate training and evaluation.
            algorithm: Non-empty algorithm name string.
            search_space: Non-empty mapping of hyperparameter name to candidate values.
            primary_metric: Non-empty metric name to optimise.
            max_configs: Maximum initial configurations; must be an int >= 1.
            random_seed: Seed for deterministic sampling.

        Returns:
            Dict with ``best_model`` (TrainedModel), ``eval_report`` (EvalReport),
            and ``rounds`` (int number of halving rounds performed).

        Raises:
            ValueError: If any input fails validation.
            TypeError: If the inner search or evaluator returns an unexpected type.
        """
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError(
                "HyperbandTuner: algorithm must be a non-empty string"
            )
        ss = search_space or {}
        if not isinstance(ss, Mapping) or not ss:
            raise ValueError(
                "HyperbandTuner: search_space must be a non-empty Mapping"
            )
        if not isinstance(primary_metric, str) or not primary_metric:
            raise ValueError(
                "HyperbandTuner: primary_metric must be a non-empty string"
            )
        if not isinstance(max_configs, int):
            raise TypeError("HyperbandTuner: max_configs must be an int")
        if max_configs < 1:
            raise ValueError("HyperbandTuner: max_configs must be >= 1")
        if not isinstance(random_seed, int):
            raise TypeError("HyperbandTuner: random_seed must be an int")
        frozen_space = {k: tuple(v) for k, v in ss.items()}
        rounds = max(1, math.ceil(math.log2(max_configs)))
        n_trials = max(1, max_configs // (2 ** (rounds - 1)))
        with Tapestry() as inner:
            split_node = _emit_value(
                value=split, _config=KnotConfig(id="split")
            )
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
            raise TypeError(
                "HyperbandTuner: search did not return a TrainedModel"
            )
        if not isinstance(report, EvalReport):
            raise TypeError(
                "HyperbandTuner: evaluator did not return an EvalReport"
            )
        return {
            "best_model": model,
            "eval_report": report,
            "rounds": rounds,
        }
