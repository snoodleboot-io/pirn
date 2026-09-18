"""``KFoldValidatorBase`` — shared per-fold wiring for the k-fold family.

``KFoldCrossValidator``, ``GroupKFoldCrossValidator``, and
``StratifiedKFoldValidator`` each: partition the dataset rows into ``k``
row-indexed folds with their own fold-producing knot, extract one
fold per index, wire a :class:`Trainer` + :class:`Evaluator` pair per
fold, and collect the per-fold reports through an
:class:`~pirn.nodes.aggregator.Aggregator` before handing them to a
final aggregate-report knot. ``TimeSeriesCrossValidator`` and
``TimeSeriesSplitterValidator`` build their fold ``SplitManifest``\\s a
different way (expanding-window / walk-forward row-count partitioning
instead of a fold-producing knot), but still share the per-fold
Trainer+Evaluator wiring and Aggregator collection step.

This base centralises exactly those shared pieces:

* :meth:`_extract_folds` — index ``k`` per-fold ``SplitManifest`` knots out of
  a fold-producing knot. The fold *strategy* belongs to that knot, chosen by
  each validator: :class:`~pirn_ml.data_prep.cross_validator.CrossValidator`
  (shuffled plain k-fold),
  :class:`~pirn_ml.data_prep.stratified_cross_validator.StratifiedCrossValidator`
  (class proportions preserved per fold), or
  :class:`~pirn_ml.data_prep.group_cross_validator.GroupCrossValidator`
  (groups never split across train and test). Every fold carries its exact
  train/test ``row_indices``.
* :meth:`_wire_folds` — build one ``Trainer`` + ``Evaluator`` pair per
  fold/split knot, with an optional per-index hyperparameters hook.
* :meth:`_collect` — fan the per-fold ``Evaluator`` outputs into a single
  :class:`Aggregator` list.

Each concrete validator keeps its own ``__init__`` (constructor
signatures are unchanged), its own validation, its own fold-generation
for the time-series pair, and its own final aggregate-report knot
(the aggregation math — mean-only vs mean±std — and the extra detail
fields genuinely differ per validator, so they are not centralised here).

Algorithm:
    1. A subclass's ``process()`` validates its own inputs.
    2. It obtains a list of per-fold ``SplitManifest`` knots, either via
       :meth:`_extract_folds` over its own fold-producing knot (the three
       k-fold validators) or its own row-count partitioning (the two
       time-series validators).
    3. It calls :meth:`_wire_folds` to get one ``Evaluator`` knot per
       fold/split, then :meth:`_collect` to fan them into an Aggregator.
    4. It returns its own aggregate-report knot fed by the collected list.

References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import KnotFactory
from pirn.core.parameter import Parameter
from pirn.nodes.aggregator import Aggregator
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_ml.evaluation.evaluator import Evaluator
from pirn_ml.training.trainer import Trainer
from pirn_ml.types.eval_report_payload import EvalReportPayload
from pirn_ml.types.split_manifest import SplitManifest


@KnotFactory.knot
async def _extract_fold(folds: tuple[SplitManifest, ...], index: int) -> SplitManifest:
    return folds[index]


class KFoldValidatorBase(SubTapestry):
    """Shared per-fold Trainer/Evaluator wiring and Aggregator collection."""

    @staticmethod
    def _extract_folds(folds_node: Knot, k: int) -> list[Knot]:
        """Index ``k`` per-fold SplitManifest knots out of a fold-producing knot."""
        fold_nodes: list[Knot] = []
        for fold_index in range(k):
            fold_index_node = Parameter(
                f"fold_index_{fold_index}",
                int,
                default=fold_index,
                _config=KnotConfig(id=f"fold_index_{fold_index}"),
            )
            fold_nodes.append(
                _extract_fold(
                    folds=folds_node,
                    index=fold_index_node,
                    _config=KnotConfig(id=f"split_{fold_index}"),
                )
            )
        return fold_nodes

    @staticmethod
    def _wire_folds(
        fold_nodes: Sequence[Knot],
        algorithm: str,
        metric_tuple: tuple[str, ...],
        hyperparameters_for_fold: Callable[[int], Mapping[str, Any]] | None = None,
    ) -> list[Knot]:
        """Wire one Trainer + Evaluator pair per fold/split knot."""
        eval_nodes: list[Knot] = []
        for fold_index, split_node in enumerate(fold_nodes):
            hyperparameters = (
                hyperparameters_for_fold(fold_index) if hyperparameters_for_fold else None
            )
            model = Trainer(
                split=split_node,
                algorithm=algorithm,
                hyperparameters=hyperparameters,
                _config=KnotConfig(id=f"train_{fold_index}"),
            )
            eval_nodes.append(
                Evaluator(
                    model=model,
                    split=split_node,
                    metrics=metric_tuple,
                    _config=KnotConfig(id=f"evaluate_{fold_index}"),
                )
            )
        return eval_nodes

    @staticmethod
    def _collect(eval_nodes: Sequence[Knot], collect_id: str) -> Knot:
        """Fan per-fold Evaluator outputs into a single Aggregator list."""
        return Aggregator(
            combine=KFoldValidatorBase._reports_in_order,
            _config=KnotConfig(id=collect_id),
            **{f"r{i}": eval_nodes[i] for i in range(len(eval_nodes))},
        )

    @staticmethod
    def _reports_in_order(**reports: EvalReportPayload) -> list[EvalReportPayload]:
        """Aggregator ``combine``: the parent evaluation reports as a list, in wiring order."""
        return list(reports.values())
