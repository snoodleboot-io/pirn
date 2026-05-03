"""``BaggingEnsembleBuilder`` — train N models on bootstrap samples and
aggregate predictions.

Classification uses majority voting; regression uses averaging. Returns
the ensemble :class:`TrainedModel` reference and its evaluation report.
"""

from __future__ import annotations

from typing import Any, ClassVar, Mapping, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.domains.ml.evaluation.evaluator import Evaluator
from pirn.domains.ml.training.ensemble_builder import EnsembleBuilder
from pirn.domains.ml.training.trainer import Trainer
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.eval_report import EvalReport
from pirn.domains.ml.types.trained_model import TrainedModel
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


@knot
async def _emit_value(value: Any) -> Any:
    return value


class BaggingEnsembleBuilder(SubTapestry):
    """Train N base models on bootstrap samples and combine via voting/averaging."""

    valid_tasks: ClassVar[frozenset[str]] = frozenset(
        {"classification", "regression"}
    )

    def __init__(
        self,
        *,
        split: Knot,
        algorithm: str,
        n_estimators: int = 10,
        task: str = "classification",
        metrics: Sequence[str],
        hyperparameters: Mapping[str, Any] | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(split, Knot):
            raise TypeError(
                "BaggingEnsembleBuilder: split must be a Knot"
            )
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError(
                "BaggingEnsembleBuilder: algorithm must be a non-empty string"
            )
        if not isinstance(n_estimators, int):
            raise TypeError(
                "BaggingEnsembleBuilder: n_estimators must be an int"
            )
        if n_estimators < 2:
            raise ValueError(
                "BaggingEnsembleBuilder: n_estimators must be >= 2"
            )
        if task not in self.valid_tasks:
            raise ValueError(
                f"BaggingEnsembleBuilder: task must be one of "
                f"{sorted(self.valid_tasks)}"
            )
        metric_tuple = tuple(metrics)
        if not metric_tuple:
            raise ValueError(
                "BaggingEnsembleBuilder: metrics must be non-empty"
            )
        for metric in metric_tuple:
            if not isinstance(metric, str) or not metric:
                raise ValueError(
                    "BaggingEnsembleBuilder: every metric name must be a "
                    "non-empty string"
                )
        if hyperparameters is not None and not isinstance(
            hyperparameters, Mapping
        ):
            raise TypeError(
                "BaggingEnsembleBuilder: hyperparameters must be a Mapping"
            )
        self._algorithm = algorithm
        self._n_estimators = n_estimators
        self._task = task
        self._metrics = metric_tuple
        self._hyperparameters = (
            dict(hyperparameters) if hyperparameters is not None else {}
        )
        super().__init__(split=split, _config=_config, **kwargs)

    async def process(
        self, split: DataSplit, **_: Any
    ) -> dict[str, Any]:
        """Train N base models, build a bagging ensemble, and return the ensemble model and its evaluation.

        Args:
            split: DataSplit used for base model training and ensemble evaluation.

        Returns:
            Dict with ``ensemble_model`` (TrainedModel), ``eval_report`` (EvalReport),
            and ``n_estimators`` (int).

        Raises:
            TypeError: If base models or the ensemble do not return the expected types.
        """
        strategy = "voting" if self._task == "classification" else "blending"
        with Tapestry() as inner:
            split_node = _emit_value(
                value=split, _config=KnotConfig(id="split")
            )
            base_models = []
            for i in range(self._n_estimators):
                hp = {**self._hyperparameters, "bootstrap_sample": i}
                model = Trainer(
                    split=split_node,
                    algorithm=self._algorithm,
                    hyperparameters=hp,
                    _config=KnotConfig(id=f"train_{i}"),
                )
                base_models.append(model)
            ensemble = EnsembleBuilder(
                models=base_models,
                strategy=strategy,
                _config=KnotConfig(id="ensemble"),
            )
            Evaluator(
                model=ensemble,
                split=split_node,
                metrics=self._metrics,
                _config=KnotConfig(id="evaluate"),
            )
        result = await self._run_inner(inner)
        ensemble_model = result.outputs["ensemble"]
        report = result.outputs["evaluate"]
        if not isinstance(ensemble_model, TrainedModel):
            raise TypeError(
                "BaggingEnsembleBuilder: ensemble did not return a TrainedModel"
            )
        if not isinstance(report, EvalReport):
            raise TypeError(
                "BaggingEnsembleBuilder: evaluator did not return an EvalReport"
            )
        return {
            "ensemble_model": ensemble_model,
            "eval_report": report,
            "n_estimators": self._n_estimators,
        }
