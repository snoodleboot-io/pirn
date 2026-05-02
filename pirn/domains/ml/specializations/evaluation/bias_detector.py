"""``BiasDetector`` — SubTapestry wrapper around :class:`FairnessAudit`.

Produces a per-group :class:`EvalReport` for the configured sensitive
columns. The wrapped :class:`FairnessAudit` does the actual per-group
metric computation; this SubTapestry exists so the audit composes with
other evaluation specializations under a uniform shape.
"""

from __future__ import annotations

from typing import Any, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.domains.ml.evaluation.fairness_audit import FairnessAudit
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.eval_report import EvalReport
from pirn.domains.ml.types.trained_model import TrainedModel
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


@knot
async def _emit_value(value: Any) -> Any:
    return value


class BiasDetector(SubTapestry):
    """Per-group bias audit wrapper around :class:`FairnessAudit`."""

    def __init__(
        self,
        *,
        model: Knot,
        split: Knot,
        sensitive_columns: Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(model, Knot):
            raise TypeError("BiasDetector: model must be a Knot")
        if not isinstance(split, Knot):
            raise TypeError("BiasDetector: split must be a Knot")
        column_tuple = tuple(sensitive_columns)
        if not column_tuple:
            raise ValueError(
                "BiasDetector: sensitive_columns must be non-empty"
            )
        for column in column_tuple:
            if not isinstance(column, str) or not column:
                raise ValueError(
                    "BiasDetector: every sensitive column name must be a "
                    "non-empty string"
                )
        self._sensitive_columns = column_tuple
        super().__init__(model=model, split=split, _config=_config, **kwargs)

    @property
    def sensitive_columns(self) -> tuple[str, ...]:
        return self._sensitive_columns

    async def process(
        self, model: TrainedModel, split: DataSplit, **_: Any
    ) -> EvalReport:
        with Tapestry() as inner:
            model_node = _emit_value(
                value=model, _config=KnotConfig(id="model")
            )
            split_node = _emit_value(
                value=split, _config=KnotConfig(id="split")
            )
            FairnessAudit(
                model=model_node,
                split=split_node,
                sensitive_columns=self._sensitive_columns,
                _config=KnotConfig(id="audit"),
            )
        inner_result = await self._run_inner(inner)
        return inner_result.outputs["audit"]
