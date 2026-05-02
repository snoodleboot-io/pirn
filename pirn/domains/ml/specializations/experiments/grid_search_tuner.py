"""``GridSearchTuner`` — exhaustive grid hyperparameter search.

Wraps :class:`HyperparamSearch` with ``strategy="grid"`` so all
candidates from the cartesian product of ``search_space`` values are
scored. Returns the :class:`TrainedModel` reference for the best
candidate, plus an :class:`EvalReport` recording its
``primary_metric`` value on the test split.
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


class GridSearchTuner(SubTapestry):
    """Wrap :class:`HyperparamSearch` with grid strategy."""

    def __init__(
        self,
        *,
        split: Knot,
        algorithm: str,
        search_space: Mapping[str, Sequence[Any]],
        primary_metric: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(split, Knot):
            raise TypeError("GridSearchTuner: split must be a Knot")
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError(
                "GridSearchTuner: algorithm must be a non-empty string"
            )
        if not isinstance(search_space, Mapping) or not search_space:
            raise ValueError(
                "GridSearchTuner: search_space must be a non-empty Mapping"
            )
        if not isinstance(primary_metric, str) or not primary_metric:
            raise ValueError(
                "GridSearchTuner: primary_metric must be a non-empty string"
            )
        self._algorithm = algorithm
        self._search_space = {k: tuple(v) for k, v in search_space.items()}
        self._primary_metric = primary_metric
        super().__init__(split=split, _config=_config, **kwargs)

    async def process(
        self, split: DataSplit, **_: Any
    ) -> dict[str, Any]:
        with Tapestry() as inner:
            split_node = _emit_value(
                value=split, _config=KnotConfig(id="split")
            )
            best = HyperparamSearch(
                split=split_node,
                algorithm=self._algorithm,
                search_space=self._search_space,
                strategy="grid",
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
                "GridSearchTuner: search did not return a TrainedModel"
            )
        if not isinstance(report, EvalReport):
            raise TypeError(
                "GridSearchTuner: evaluator did not return an EvalReport"
            )
        return {"best_model": model, "eval_report": report}
