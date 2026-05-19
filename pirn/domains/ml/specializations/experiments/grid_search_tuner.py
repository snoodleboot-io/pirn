"""``GridSearchTuner`` — exhaustive grid hyperparameter search.

Wraps :class:`HyperparamSearch` with ``strategy="grid"`` so all
candidates from the cartesian product of ``search_space`` values are
scored. Returns the :class:`ModelManifest` reference for the best
candidate, plus an :class:`EvalMetadata` recording its
``primary_metric`` value on the test split.

Algorithm:
    1. Receive ``split`` (SplitManifest), ``algorithm``, ``search_space``, and
       ``primary_metric`` via process().
    2. Validate all inputs.
    3. Wire HyperparamSearch (grid) + Evaluator in an inner Tapestry.
    4. Run via _run_inner() and return best_model and eval_report.

Math:
    Search space: cartesian product of all parameter value lists.
        |configs| = product(len(v) for v in search_space.values())

    Best config: theta* = argmax_{theta in configs} metric(eval(model(theta), split))

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
from pirn.domains.ml.types.eval_report_payload import EvalReportPayload
from pirn.domains.ml.types.model_manifest import ModelManifest
from pirn.domains.ml.types.split_manifest import SplitManifest
from pirn.nodes.sub_tapestry import SubTapestry


@knot
async def _emit_value(value: Any) -> Any:
    return value


@knot
async def _combine_search_eval(
    best_model: ModelManifest,
    eval_report: EvalReportPayload,
) -> dict[str, Any]:
    return {"best_model": best_model, "eval_report": eval_report}


class GridSearchTuner(SubTapestry):
    """Wrap :class:`HyperparamSearch` with grid strategy."""

    def __init__(
        self,
        *,
        split: Knot,
        algorithm: Knot | str,
        search_space: Knot | Mapping[str, Sequence[Any]],
        primary_metric: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            split=split,
            algorithm=algorithm,
            search_space=search_space,
            primary_metric=primary_metric,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        split: SplitManifest,
        algorithm: str = "",
        search_space: Mapping[str, Sequence[Any]] | None = None,
        primary_metric: str = "",
        **_: Any,
    ) -> Any:
        """Run an exhaustive grid search over the search space and return the best model and its evaluation report.

        Args:
            split: SplitManifest used for candidate training and evaluation.
            algorithm: Non-empty algorithm name string.
            search_space: Non-empty mapping of hyperparameter name to candidate values.
            primary_metric: Non-empty metric name to report.

        Returns:
            Dict with ``best_model`` (ModelManifest) and ``eval_report`` (EvalMetadata).

        Raises:
            ValueError: If any input fails validation.
            TypeError: If the inner search or evaluator returns an unexpected type.
        """
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError("GridSearchTuner: algorithm must be a non-empty string")
        ss = search_space or {}
        if not isinstance(ss, Mapping) or not ss:
            raise ValueError("GridSearchTuner: search_space must be a non-empty Mapping")
        if not isinstance(primary_metric, str) or not primary_metric:
            raise ValueError("GridSearchTuner: primary_metric must be a non-empty string")
        frozen_space = {k: tuple(v) for k, v in ss.items()}
        split_node = _emit_value(value=split, _config=KnotConfig(id="split"))
        best = HyperparamSearch(
            split=split_node,
            algorithm=algorithm,
            search_space=frozen_space,
            strategy="grid",
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
