"""``_KFoldValidatorBase`` — shared per-fold wiring for the k-fold family.

``KFoldCrossValidator``, ``GroupKFoldCrossValidator``, and
``StratifiedKFoldValidator`` each: request ``k`` logical folds from
:class:`~pirn_ml.data_prep.cross_validator.CrossValidator`, extract one
fold per index, wire a :class:`Trainer` + :class:`Evaluator` pair per
fold, and collect the per-fold reports through an
:class:`~pirn.nodes.aggregator.Aggregator` before handing them to a
final aggregate-report knot. ``TimeSeriesCrossValidator`` and
``TimeSeriesSplitterValidator`` build their fold ``SplitManifest``\\s a
different way (expanding-window / walk-forward row-count partitioning
instead of ``CrossValidator``), but still share the per-fold
Trainer+Evaluator wiring and Aggregator collection step.

This base centralises exactly those shared pieces:

* :meth:`_extract_folds_via_cross_validator` — the "plain"/"group" k-fold
  split strategy (a :class:`~pirn.nodes.aggregator.Aggregator`-free,
  ``CrossValidator``-backed extraction of ``k`` logical folds). It is a
  plain method (not a ``@staticmethod``) so a future group- or
  stratify-aware validator can override it with real group/stratify-aware
  partitioning; today ``KFoldCrossValidator``, ``GroupKFoldCrossValidator``,
  and ``StratifiedKFoldValidator`` all call the identical base
  implementation — grouping and stratification are recorded as metadata
  only, since the orchestration-layer ``CrossValidator`` does not itself
  partition by group or stratify column.
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
       :meth:`_extract_folds_via_cross_validator` (the three CrossValidator-
       backed validators) or its own row-count partitioning (the two
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
from pirn.core.knot_factory import knot
from pirn.core.parameter import Parameter
from pirn.nodes.aggregator import Aggregator
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_ml.data_prep.cross_validator import CrossValidator
from pirn_ml.evaluation.evaluator import Evaluator
from pirn_ml.training.trainer import Trainer
from pirn_ml.types.split_manifest import SplitManifest


@knot
async def _extract_fold(folds: tuple[SplitManifest, ...], index: int) -> SplitManifest:
    return folds[index]


class _KFoldValidatorBase(SubTapestry):
    """Shared per-fold Trainer/Evaluator wiring and Aggregator collection."""

    def _extract_folds_via_cross_validator(self, dataset: Knot, k: int) -> list[Knot]:
        """ "Plain"/"group" k-fold split strategy: k logical folds via CrossValidator.

        Overridable so a concrete group-aware or stratify-aware CrossValidator
        can be substituted later; the base implementation used by
        KFoldCrossValidator, GroupKFoldCrossValidator, and
        StratifiedKFoldValidator today is identical for all three.
        """
        folds_node = CrossValidator(
            dataset=dataset,
            k=k,
            _config=KnotConfig(id="folds"),
        )
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
            combine=lambda **kw: list(kw.values()),
            _config=KnotConfig(id=collect_id),
            **{f"r{i}": eval_nodes[i] for i in range(len(eval_nodes))},
        )
