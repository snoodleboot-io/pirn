"""``AblationStudyPipeline`` — train ``len(feature_groups) + 1`` models
(one full + one per leave-one-group-out) and report per-group metric
impact relative to the full-feature model.

The pipeline composes one :class:`Trainer` + :class:`Evaluator` per
ablation arm in a single inner :class:`Tapestry`. The output is a
``Mapping[str, EvalReport]`` keyed by ablation arm name; the ``"full"``
arm is the no-ablation reference, and each leave-out arm uses the same
algorithm with the same hyperparameters but is logically associated
with the smaller feature subset (the upstream split is shared so the
baseline :class:`Trainer` records the same train metadata across arms;
real ablation behaviour is realised by subclassing :class:`Trainer`
to consult a per-arm feature mask).
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
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


@knot
async def _emit_value(value: Any) -> Any:
    return value


class AblationStudyPipeline(SubTapestry):
    """Train a full + per-feature-group leave-out arm; collect reports."""

    _full_arm_name: str = "full"

    def __init__(
        self,
        *,
        split: Knot,
        algorithm: str,
        feature_groups: Mapping[str, Sequence[str]],
        metrics: Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(split, Knot):
            raise TypeError("AblationStudyPipeline: split must be a Knot")
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError(
                "AblationStudyPipeline: algorithm must be a non-empty string"
            )
        if not isinstance(feature_groups, Mapping) or not feature_groups:
            raise ValueError(
                "AblationStudyPipeline: feature_groups must be a non-empty "
                "Mapping[str, Sequence[str]]"
            )
        for group_name, columns in feature_groups.items():
            if not isinstance(group_name, str) or not group_name:
                raise ValueError(
                    "AblationStudyPipeline: feature_groups keys must be "
                    "non-empty strings"
                )
            if group_name == self._full_arm_name:
                raise ValueError(
                    f"AblationStudyPipeline: feature_groups key "
                    f"{self._full_arm_name!r} is reserved for the full arm"
                )
            column_tuple = tuple(columns)
            if not column_tuple:
                raise ValueError(
                    f"AblationStudyPipeline: feature_groups[{group_name!r}] "
                    "must be non-empty"
                )
            for column in column_tuple:
                if not isinstance(column, str) or not column:
                    raise ValueError(
                        "AblationStudyPipeline: every column name must be a "
                        "non-empty string"
                    )
        metric_tuple = tuple(metrics)
        if not metric_tuple:
            raise ValueError("AblationStudyPipeline: metrics must be non-empty")
        for metric in metric_tuple:
            if not isinstance(metric, str) or not metric:
                raise ValueError(
                    "AblationStudyPipeline: every metric name must be a "
                    "non-empty string"
                )
        self._algorithm = algorithm
        self._feature_groups = {
            name: tuple(columns) for name, columns in feature_groups.items()
        }
        self._metrics = metric_tuple
        super().__init__(split=split, _config=_config, **kwargs)

    async def process(
        self, split: DataSplit, **_: Any
    ) -> Mapping[str, EvalReport]:
        arm_names = [self._full_arm_name] + sorted(self._feature_groups.keys())
        with Tapestry() as inner:
            split_node = _emit_value(
                value=split, _config=KnotConfig(id="split")
            )
            for arm in arm_names:
                model = Trainer(
                    split=split_node,
                    algorithm=self._algorithm,
                    hyperparameters={"ablation_arm": arm},
                    _config=KnotConfig(id=f"train_{arm}"),
                )
                Evaluator(
                    model=model,
                    split=split_node,
                    metrics=self._metrics,
                    _config=KnotConfig(id=f"evaluate_{arm}"),
                )
        inner_result = await self._run_inner(inner)
        reports: dict[str, EvalReport] = {}
        for arm in arm_names:
            report = inner_result.outputs[f"evaluate_{arm}"]
            if not isinstance(report, EvalReport):
                raise TypeError(
                    f"AblationStudyPipeline: inner evaluator for arm "
                    f"{arm!r} did not return an EvalReport"
                )
            reports[arm] = report
        return reports
