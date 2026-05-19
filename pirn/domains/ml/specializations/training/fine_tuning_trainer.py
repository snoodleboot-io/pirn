"""``FineTuningTrainer`` — load a pretrained model, freeze base layers, and
fine-tune the head on a new dataset.

Returns the fine-tuned :class:`ModelManifest` and its evaluation report.

Algorithm:
    1. Receive ``split``, ``pretrained_model_id``, ``algorithm``,
       ``metrics``, ``frozen_layers``, and ``hyperparameters`` via process().
    2. Validate all inputs.
    3. Wire Trainer + Evaluator in an inner Tapestry.
    4. Run via _run_inner() and return model, eval report, and metadata.

Math:
    Trainable parameters: theta_head = all parameters excluding the first
    frozen_layers frozen layers.

    Fine-tuning gradient update (SGD example):
        theta_head <- theta_head - lr * grad_L(theta_head)

    Frozen layers have zero gradient contribution: grad_L(theta_frozen) = 0.

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
from pirn.domains.ml.training.trainer import Trainer
from pirn.domains.ml.types.eval_report_payload import EvalReportPayload
from pirn.domains.ml.types.model_manifest import ModelManifest
from pirn.domains.ml.types.split_manifest import SplitManifest
from pirn.nodes.sub_tapestry import SubTapestry


@knot
async def _emit_value(value: Any) -> Any:
    return value


@knot
async def _combine_finetune_eval(
    model: ModelManifest,
    eval_report: EvalReportPayload,
    pretrained_model_id: str,
    frozen_layers: int,
) -> dict[str, Any]:
    return {
        "model": model,
        "eval_report": eval_report,
        "pretrained_model_id": pretrained_model_id,
        "frozen_layers": frozen_layers,
    }


class FineTuningTrainer(SubTapestry):
    """Freeze the base of a pretrained model and fine-tune the head."""

    def __init__(
        self,
        *,
        split: Knot,
        pretrained_model_id: Knot | str,
        algorithm: Knot | str,
        metrics: Knot | Sequence[str],
        frozen_layers: Knot | int = 0,
        hyperparameters: Knot | Mapping[str, Any] | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            split=split,
            pretrained_model_id=pretrained_model_id,
            algorithm=algorithm,
            metrics=metrics,
            frozen_layers=frozen_layers,
            hyperparameters=hyperparameters,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        split: SplitManifest,
        pretrained_model_id: str = "",
        algorithm: str = "",
        metrics: Sequence[str] = (),
        frozen_layers: int = 0,
        hyperparameters: Mapping[str, Any] | None = None,
        **_: Any,
    ) -> Any:
        """Fine-tune the pretrained model and return the resulting model and its evaluation.

        Args:
            split: SplitManifest used for fine-tuning and evaluation.
            pretrained_model_id: Non-empty identifier of the pretrained model.
            algorithm: Non-empty algorithm identifier.
            metrics: Non-empty sequence of metric names.
            frozen_layers: Number of layers to freeze; must be an int >= 0.
            hyperparameters: Optional mapping of additional hyperparameters.

        Returns:
            Dict with ``model`` (ModelManifest), ``eval_report`` (EvalMetadata),
            ``pretrained_model_id`` (str), and ``frozen_layers`` (int).

        Raises:
            ValueError: If any input fails validation.
            TypeError: If the inner trainer or evaluator returns an unexpected type.
        """
        if not isinstance(pretrained_model_id, str) or not pretrained_model_id:
            raise ValueError("FineTuningTrainer: pretrained_model_id must be a non-empty string")
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError("FineTuningTrainer: algorithm must be a non-empty string")
        if not isinstance(frozen_layers, int):
            raise TypeError("FineTuningTrainer: frozen_layers must be an int")
        if frozen_layers < 0:
            raise ValueError("FineTuningTrainer: frozen_layers must be >= 0")
        metric_tuple = tuple(metrics)
        if not metric_tuple:
            raise ValueError("FineTuningTrainer: metrics must be non-empty")
        for metric in metric_tuple:
            if not isinstance(metric, str) or not metric:
                raise ValueError("FineTuningTrainer: every metric name must be a non-empty string")
        if hyperparameters is not None and not isinstance(hyperparameters, Mapping):
            raise TypeError("FineTuningTrainer: hyperparameters must be a Mapping")
        hp = dict(hyperparameters) if hyperparameters is not None else {}
        hp["pretrained_model_id"] = pretrained_model_id
        hp["frozen_layers"] = frozen_layers
        split_node = _emit_value(value=split, _config=KnotConfig(id="split"))
        trained = Trainer(
            split=split_node,
            algorithm=algorithm,
            hyperparameters=hp,
            _config=KnotConfig(id="train"),
        )
        evaluated = Evaluator(
            model=trained,
            split=split_node,
            metrics=metric_tuple,
            _config=KnotConfig(id="evaluate"),
        )
        pmid_node = _emit_value(
            value=pretrained_model_id, _config=KnotConfig(id="pretrained_model_id")
        )
        fl_node = _emit_value(value=frozen_layers, _config=KnotConfig(id="frozen_layers"))
        return _combine_finetune_eval(
            model=trained,
            eval_report=evaluated,
            pretrained_model_id=pmid_node,
            frozen_layers=fl_node,
            _config=KnotConfig(id="combine"),
        )
