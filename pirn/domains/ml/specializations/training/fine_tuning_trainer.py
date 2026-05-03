"""``FineTuningTrainer`` — load a pretrained model, freeze base layers, and
fine-tune the head on a new dataset.

Returns the fine-tuned :class:`TrainedModel` and its evaluation report.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

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


class FineTuningTrainer(SubTapestry):
    """Freeze the base of a pretrained model and fine-tune the head."""

    def __init__(
        self,
        *,
        split: Knot,
        pretrained_model_id: str,
        algorithm: str,
        metrics: Sequence[str],
        frozen_layers: int = 0,
        hyperparameters: Mapping[str, Any] | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(split, Knot):
            raise TypeError("FineTuningTrainer: split must be a Knot")
        if not isinstance(pretrained_model_id, str) or not pretrained_model_id:
            raise ValueError(
                "FineTuningTrainer: pretrained_model_id must be a non-empty "
                "string"
            )
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError(
                "FineTuningTrainer: algorithm must be a non-empty string"
            )
        if not isinstance(frozen_layers, int):
            raise TypeError(
                "FineTuningTrainer: frozen_layers must be an int"
            )
        if frozen_layers < 0:
            raise ValueError(
                "FineTuningTrainer: frozen_layers must be >= 0"
            )
        metric_tuple = tuple(metrics)
        if not metric_tuple:
            raise ValueError("FineTuningTrainer: metrics must be non-empty")
        for metric in metric_tuple:
            if not isinstance(metric, str) or not metric:
                raise ValueError(
                    "FineTuningTrainer: every metric name must be a "
                    "non-empty string"
                )
        if hyperparameters is not None and not isinstance(
            hyperparameters, Mapping
        ):
            raise TypeError(
                "FineTuningTrainer: hyperparameters must be a Mapping"
            )
        self._pretrained_model_id = pretrained_model_id
        self._algorithm = algorithm
        self._frozen_layers = frozen_layers
        self._metrics = metric_tuple
        self._hyperparameters = (
            dict(hyperparameters) if hyperparameters is not None else {}
        )
        super().__init__(split=split, _config=_config, **kwargs)

    async def process(
        self, split: DataSplit, **_: Any
    ) -> dict[str, Any]:
        """Fine-tune the pretrained model and return the resulting model and its evaluation.

        Args:
            split: DataSplit used for fine-tuning and evaluation.

        Returns:
            Dict with ``model`` (TrainedModel), ``eval_report`` (EvalReport),
            ``pretrained_model_id`` (str), and ``frozen_layers`` (int).

        Raises:
            TypeError: If the inner trainer or evaluator returns an unexpected type.
        """
        hp = {
            **self._hyperparameters,
            "pretrained_model_id": self._pretrained_model_id,
            "frozen_layers": self._frozen_layers,
        }
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
                "FineTuningTrainer: trainer did not return a TrainedModel"
            )
        if not isinstance(report, EvalReport):
            raise TypeError(
                "FineTuningTrainer: evaluator did not return an EvalReport"
            )
        return {
            "model": trained_model,
            "eval_report": report,
            "pretrained_model_id": self._pretrained_model_id,
            "frozen_layers": self._frozen_layers,
        }
