"""``SelfSupervisedPretrainer`` — pretrain via a self-supervised objective,
then fine-tune on a labeled dataset.

The pretraining objective (e.g. masked feature prediction) is encoded
in the ``pretrain_algorithm`` parameter. Fine-tuning uses the configured
``finetune_algorithm`` on the labeled :class:`SplitManifest`.

Algorithm:
    1. Receive ``split``, ``pretrain_algorithm``, ``finetune_algorithm``,
       ``metrics``, ``pretrain_hyperparameters``, and
       ``finetune_hyperparameters`` via process().
    2. Validate all inputs.
    3. Wire pretrain Trainer → finetune Trainer → Evaluator in an inner Tapestry.
    4. Run via _run_inner() and return model, eval report, and algorithm names.


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
async def _combine_self_supervised_result(
    model: ModelManifest,
    eval_report: EvalReportPayload,
    pretrain_algorithm: str,
    finetune_algorithm: str,
) -> dict[str, Any]:
    return {
        "model": model,
        "eval_report": eval_report,
        "pretrain_algorithm": pretrain_algorithm,
        "finetune_algorithm": finetune_algorithm,
    }


class SelfSupervisedPretrainer(SubTapestry):
    """Pretrain self-supervised then fine-tune on labeled data."""

    def __init__(
        self,
        *,
        split: Knot,
        pretrain_algorithm: Knot | str,
        finetune_algorithm: Knot | str,
        metrics: Knot | Sequence[str],
        pretrain_hyperparameters: Knot | Mapping[str, Any] | None = None,
        finetune_hyperparameters: Knot | Mapping[str, Any] | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            split=split,
            pretrain_algorithm=pretrain_algorithm,
            finetune_algorithm=finetune_algorithm,
            metrics=metrics,
            pretrain_hyperparameters=pretrain_hyperparameters,
            finetune_hyperparameters=finetune_hyperparameters,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        split: SplitManifest,
        pretrain_algorithm: str = "",
        finetune_algorithm: str = "",
        metrics: Sequence[str] = (),
        pretrain_hyperparameters: Mapping[str, Any] | None = None,
        finetune_hyperparameters: Mapping[str, Any] | None = None,
        **_: Any,
    ) -> Any:
        """Pretrain via a self-supervised objective then fine-tune on labeled data.

        Args:
            split: SplitManifest used for both the self-supervised pretraining and
                the supervised fine-tuning pass.
            pretrain_algorithm: Non-empty algorithm identifier for pretraining.
            finetune_algorithm: Non-empty algorithm identifier for fine-tuning.
            metrics: Non-empty sequence of metric names.
            pretrain_hyperparameters: Optional mapping of pretraining hyperparameters.
            finetune_hyperparameters: Optional mapping of fine-tuning hyperparameters.

        Returns:
            Dict with ``model`` (ModelManifest), ``eval_report`` (EvalMetadata),
            ``pretrain_algorithm`` (str), and ``finetune_algorithm`` (str).

        Raises:
            ValueError: If any input fails validation.
            TypeError: If any inner trainer or evaluator returns an unexpected type.
        """
        if not isinstance(pretrain_algorithm, str) or not pretrain_algorithm:
            raise ValueError(
                "SelfSupervisedPretrainer: pretrain_algorithm must be a non-empty string"
            )
        if not isinstance(finetune_algorithm, str) or not finetune_algorithm:
            raise ValueError(
                "SelfSupervisedPretrainer: finetune_algorithm must be a non-empty string"
            )
        metric_tuple = tuple(metrics)
        if not metric_tuple:
            raise ValueError("SelfSupervisedPretrainer: metrics must be non-empty")
        for metric in metric_tuple:
            if not isinstance(metric, str) or not metric:
                raise ValueError(
                    "SelfSupervisedPretrainer: every metric name must be a non-empty string"
                )
        if pretrain_hyperparameters is not None and not isinstance(
            pretrain_hyperparameters, Mapping
        ):
            raise TypeError("SelfSupervisedPretrainer: pretrain_hyperparameters must be a Mapping")
        if finetune_hyperparameters is not None and not isinstance(
            finetune_hyperparameters, Mapping
        ):
            raise TypeError("SelfSupervisedPretrainer: finetune_hyperparameters must be a Mapping")
        pretrain_hp = dict(pretrain_hyperparameters) if pretrain_hyperparameters is not None else {}
        finetune_hp = dict(finetune_hyperparameters) if finetune_hyperparameters is not None else {}
        split_node = _emit_value(value=split, _config=KnotConfig(id="split"))
        pretrained = Trainer(
            split=split_node,
            algorithm=pretrain_algorithm,
            hyperparameters={**pretrain_hp, "self_supervised": True},
            _config=KnotConfig(id="pretrain"),
        )
        finetuned = Trainer(
            split=split_node,
            algorithm=finetune_algorithm,
            hyperparameters={**finetune_hp, "pretrained_from": pretrained.knot_id},
            _config=KnotConfig(id="finetune"),
        )
        evaluated = Evaluator(
            model=finetuned,
            split=split_node,
            metrics=metric_tuple,
            _config=KnotConfig(id="evaluate"),
        )
        pretrain_alg_node = _emit_value(
            value=pretrain_algorithm, _config=KnotConfig(id="pretrain_algorithm")
        )
        finetune_alg_node = _emit_value(
            value=finetune_algorithm, _config=KnotConfig(id="finetune_algorithm")
        )
        return _combine_self_supervised_result(
            model=finetuned,
            eval_report=evaluated,
            pretrain_algorithm=pretrain_alg_node,
            finetune_algorithm=finetune_alg_node,
            _config=KnotConfig(id="combine"),
        )
