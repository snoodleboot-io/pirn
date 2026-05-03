"""``SelfSupervisedPretrainer`` — pretrain via a self-supervised objective,
then fine-tune on a labeled dataset.

The pretraining objective (e.g. masked feature prediction) is encoded
in the ``pretrain_algorithm`` parameter. Fine-tuning uses the configured
``finetune_algorithm`` on the labeled :class:`DataSplit`.
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


class SelfSupervisedPretrainer(SubTapestry):
    """Pretrain self-supervised then fine-tune on labeled data."""

    def __init__(
        self,
        *,
        split: Knot,
        pretrain_algorithm: str,
        finetune_algorithm: str,
        metrics: Sequence[str],
        pretrain_hyperparameters: Mapping[str, Any] | None = None,
        finetune_hyperparameters: Mapping[str, Any] | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(split, Knot):
            raise TypeError("SelfSupervisedPretrainer: split must be a Knot")
        if not isinstance(pretrain_algorithm, str) or not pretrain_algorithm:
            raise ValueError(
                "SelfSupervisedPretrainer: pretrain_algorithm must be a "
                "non-empty string"
            )
        if not isinstance(finetune_algorithm, str) or not finetune_algorithm:
            raise ValueError(
                "SelfSupervisedPretrainer: finetune_algorithm must be a "
                "non-empty string"
            )
        metric_tuple = tuple(metrics)
        if not metric_tuple:
            raise ValueError(
                "SelfSupervisedPretrainer: metrics must be non-empty"
            )
        for metric in metric_tuple:
            if not isinstance(metric, str) or not metric:
                raise ValueError(
                    "SelfSupervisedPretrainer: every metric name must be a "
                    "non-empty string"
                )
        if pretrain_hyperparameters is not None and not isinstance(
            pretrain_hyperparameters, Mapping
        ):
            raise TypeError(
                "SelfSupervisedPretrainer: pretrain_hyperparameters must be a "
                "Mapping"
            )
        if finetune_hyperparameters is not None and not isinstance(
            finetune_hyperparameters, Mapping
        ):
            raise TypeError(
                "SelfSupervisedPretrainer: finetune_hyperparameters must be a "
                "Mapping"
            )
        self._pretrain_algorithm = pretrain_algorithm
        self._finetune_algorithm = finetune_algorithm
        self._metrics = metric_tuple
        self._pretrain_hp = (
            dict(pretrain_hyperparameters)
            if pretrain_hyperparameters is not None
            else {}
        )
        self._finetune_hp = (
            dict(finetune_hyperparameters)
            if finetune_hyperparameters is not None
            else {}
        )
        super().__init__(split=split, _config=_config, **kwargs)

    async def process(
        self, split: DataSplit, **_: Any
    ) -> dict[str, Any]:
        """Pretrain via a self-supervised objective then fine-tune on labeled data.

        Args:
            split: DataSplit used for both the self-supervised pretraining and
                the supervised fine-tuning pass.

        Returns:
            Dict with ``model`` (TrainedModel), ``eval_report`` (EvalReport),
            ``pretrain_algorithm`` (str), and ``finetune_algorithm`` (str).

        Raises:
            TypeError: If any inner trainer or evaluator returns an unexpected type.
        """
        with Tapestry() as inner:
            split_node = _emit_value(
                value=split, _config=KnotConfig(id="split")
            )
            pretrained = Trainer(
                split=split_node,
                algorithm=self._pretrain_algorithm,
                hyperparameters={
                    **self._pretrain_hp,
                    "self_supervised": True,
                },
                _config=KnotConfig(id="pretrain"),
            )
            finetuned = Trainer(
                split=split_node,
                algorithm=self._finetune_algorithm,
                hyperparameters={
                    **self._finetune_hp,
                    "pretrained_from": pretrained.knot_id,
                },
                _config=KnotConfig(id="finetune"),
            )
            Evaluator(
                model=finetuned,
                split=split_node,
                metrics=self._metrics,
                _config=KnotConfig(id="evaluate"),
            )
        result = await self._run_inner(inner)
        trained_model = result.outputs["finetune"]
        report = result.outputs["evaluate"]
        if not isinstance(trained_model, TrainedModel):
            raise TypeError(
                "SelfSupervisedPretrainer: fine-tune trainer did not return "
                "a TrainedModel"
            )
        if not isinstance(report, EvalReport):
            raise TypeError(
                "SelfSupervisedPretrainer: evaluator did not return an "
                "EvalReport"
            )
        return {
            "model": trained_model,
            "eval_report": report,
            "pretrain_algorithm": self._pretrain_algorithm,
            "finetune_algorithm": self._finetune_algorithm,
        }
