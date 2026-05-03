"""``LRSchedulerTrainer`` — wrap a neural-net trainer with a learning-rate
scheduler.

Supports ``step``, ``cosine``, and ``reduce_on_plateau`` scheduling
strategies. Returns the trained model, evaluation report, and the
scheduler strategy used.
"""

from __future__ import annotations

from typing import Any, ClassVar, Mapping, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.domains.ml.evaluation.evaluator import Evaluator
from pirn.domains.ml.training.trainer import Trainer
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.eval_report import EvalReport
from pirn.domains.ml.types.trained_model import TrainedModel
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


@knot
async def _emit_value(value: Any) -> Any:
    return value


class LRSchedulerTrainer(SubTapestry):
    """Train a neural net with a configurable learning-rate scheduler."""

    valid_schedulers: ClassVar[frozenset[str]] = frozenset(
        {"step", "cosine", "reduce_on_plateau"}
    )

    def __init__(
        self,
        *,
        split: Knot,
        algorithm: str,
        scheduler: str = "cosine",
        metrics: Sequence[str],
        hyperparameters: Mapping[str, Any] | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(split, Knot):
            raise TypeError("LRSchedulerTrainer: split must be a Knot")
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError(
                "LRSchedulerTrainer: algorithm must be a non-empty string"
            )
        if scheduler not in self.valid_schedulers:
            raise ValueError(
                f"LRSchedulerTrainer: scheduler must be one of "
                f"{sorted(self.valid_schedulers)}"
            )
        metric_tuple = tuple(metrics)
        if not metric_tuple:
            raise ValueError("LRSchedulerTrainer: metrics must be non-empty")
        for metric in metric_tuple:
            if not isinstance(metric, str) or not metric:
                raise ValueError(
                    "LRSchedulerTrainer: every metric name must be a "
                    "non-empty string"
                )
        if hyperparameters is not None and not isinstance(
            hyperparameters, Mapping
        ):
            raise TypeError(
                "LRSchedulerTrainer: hyperparameters must be a Mapping"
            )
        self._algorithm = algorithm
        self._scheduler = scheduler
        self._metrics = metric_tuple
        self._hyperparameters = (
            dict(hyperparameters) if hyperparameters is not None else {}
        )
        super().__init__(split=split, _config=_config, **kwargs)

    async def process(
        self, split: DataSplit, **_: Any
    ) -> dict[str, Any]:
        """Train the model with a learning-rate scheduler and return the model, evaluation, and scheduler info.

        Args:
            split: DataSplit used for training and evaluation.

        Returns:
            Dict with ``model`` (TrainedModel), ``eval_report`` (EvalReport),
            and ``scheduler`` (str name of the scheduler used).

        Raises:
            TypeError: If the inner trainer or evaluator returns an unexpected type.
        """
        hp = {**self._hyperparameters, "lr_scheduler": self._scheduler}
        with Tapestry() as inner:
            split_node = _emit_value(
                value=split, _config=KnotConfig(id="split")
            )
            model = Trainer(
                split=split_node,
                algorithm=self._algorithm,
                hyperparameters=hp,
                _config=KnotConfig(id="train"),
            )
            Evaluator(
                model=model,
                split=split_node,
                metrics=self._metrics,
                _config=KnotConfig(id="evaluate"),
            )
        result = await self._run_inner(inner)
        trained_model = result.outputs["train"]
        report = result.outputs["evaluate"]
        if not isinstance(trained_model, TrainedModel):
            raise TypeError(
                "LRSchedulerTrainer: trainer did not return a TrainedModel"
            )
        if not isinstance(report, EvalReport):
            raise TypeError(
                "LRSchedulerTrainer: evaluator did not return an EvalReport"
            )
        return {
            "model": trained_model,
            "eval_report": report,
            "scheduler": self._scheduler,
        }
