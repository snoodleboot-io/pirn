"""``BlendingEnsembleBuilder`` — train base models on 80% of data, blend
predictions on 20% holdout using a weighted average.

Returns the blended ensemble :class:`TrainedModel` and its evaluation
report.

Algorithm:
    1. Receive ``split``, ``base_algorithms``, and ``metrics`` via process().
    2. Validate all inputs.
    3. Create 80/20 blend split, wire base Trainers + EnsembleBuilder +
       Evaluator in an inner Tapestry.
    4. Run via _run_inner() and return ensemble model and eval report.


References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from typing import Any, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.domains.ml.evaluation.evaluator import Evaluator
from pirn.domains.ml.training.ensemble_builder import EnsembleBuilder
from pirn.domains.ml.training.trainer import Trainer
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.eval_report import EvalReport
from pirn.domains.ml.types.ml_dataset import MLDataset
from pirn.domains.ml.types.trained_model import TrainedModel
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


@knot
async def _emit_value(value: Any) -> Any:
    return value


class BlendingEnsembleBuilder(SubTapestry):
    """Train base models on an 80/20 split and blend on the holdout."""

    def __init__(
        self,
        *,
        split: Knot,
        base_algorithms: Knot | Sequence[str],
        metrics: Knot | Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            split=split,
            base_algorithms=base_algorithms,
            metrics=metrics,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        split: DataSplit,
        base_algorithms: Sequence[str] = (),
        metrics: Sequence[str] = (),
        **_: Any,
    ) -> dict[str, Any]:
        """Train base models on 80% of training data and blend on 20% holdout.

        Args:
            split: DataSplit whose train partition is further divided 80/20
                for base training and blending.
            base_algorithms: At least two non-empty algorithm identifiers.
            metrics: Non-empty sequence of metric names.

        Returns:
            Dict with ``ensemble_model`` (TrainedModel), ``eval_report`` (EvalReport),
            and ``n_base_models`` (int).

        Raises:
            ValueError: If fewer than two algorithms or metrics is empty.
            TypeError: If base models or the ensemble do not return the expected types.
        """
        base_tuple = tuple(base_algorithms)
        if len(base_tuple) < 2:
            raise ValueError(
                "BlendingEnsembleBuilder: at least two base_algorithms are required"
            )
        for alg in base_tuple:
            if not isinstance(alg, str) or not alg:
                raise ValueError(
                    "BlendingEnsembleBuilder: every base algorithm must be a non-empty string"
                )
        metric_tuple = tuple(metrics)
        if not metric_tuple:
            raise ValueError("BlendingEnsembleBuilder: metrics must be non-empty")
        for metric in metric_tuple:
            if not isinstance(metric, str) or not metric:
                raise ValueError(
                    "BlendingEnsembleBuilder: every metric name must be a non-empty string"
                )
        train_rows = split.train.row_count
        blend_rows = max(1, train_rows // 5)
        base_rows = train_rows - blend_rows

        base_train_ds = MLDataset(
            name=f"{split.train.name}:blend_train",
            feature_names=split.train.feature_names,
            target_name=split.train.target_name,
            row_count=base_rows,
            source_uri=split.train.source_uri,
        )
        blend_test_ds = MLDataset(
            name=f"{split.train.name}:blend_holdout",
            feature_names=split.train.feature_names,
            target_name=split.train.target_name,
            row_count=blend_rows,
            source_uri=split.train.source_uri,
        )
        blend_split = DataSplit(train=base_train_ds, test=blend_test_ds)

        with Tapestry() as inner:
            split_node = _emit_value(
                value=blend_split, _config=KnotConfig(id="blend_split")
            )
            base_models = []
            for i, alg in enumerate(base_tuple):
                model = Trainer(
                    split=split_node,
                    algorithm=alg,
                    _config=KnotConfig(id=f"base_{i}"),
                )
                base_models.append(model)
            ensemble = EnsembleBuilder(
                models=base_models,
                strategy="blending",
                _config=KnotConfig(id="ensemble"),
            )
            Evaluator(
                model=ensemble,
                split=split_node,
                metrics=metric_tuple,
                _config=KnotConfig(id="evaluate"),
            )
        result = await self._run_inner(inner)
        ensemble_model = result.outputs["ensemble"]
        report = result.outputs["evaluate"]
        if not isinstance(ensemble_model, TrainedModel):
            raise TypeError(
                "BlendingEnsembleBuilder: ensemble did not return a TrainedModel"
            )
        if not isinstance(report, EvalReport):
            raise TypeError(
                "BlendingEnsembleBuilder: evaluator did not return an EvalReport"
            )
        return {
            "ensemble_model": ensemble_model,
            "eval_report": report,
            "n_base_models": len(base_tuple),
        }
