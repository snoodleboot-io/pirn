"""``BiasDetector`` — SubTapestry wrapper around :class:`FairnessAudit`.

Produces a per-group :class:`EvalReport` for the configured sensitive
columns. The wrapped :class:`FairnessAudit` does the actual per-group
metric computation; this SubTapestry exists so the audit composes with
other evaluation specializations under a uniform shape.

Algorithm:
    1. Receive ``model`` (TrainedModel), ``split`` (DataSplit), and
       ``sensitive_columns`` (Sequence[str]) via process().
    2. Validate sensitive_columns is non-empty and all elements are non-empty strings.
    3. Wire an inner Tapestry with FairnessAudit for each sensitive column.
    4. Run the inner Tapestry via _run_inner() and return the audit EvalReport.


References:
    N/A — pirn-native implementation.
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
        sensitive_columns: Knot | Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            model=model,
            split=split,
            sensitive_columns=sensitive_columns,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        model: TrainedModel,
        split: DataSplit,
        sensitive_columns: Sequence[str] = (),
        **_: Any,
    ) -> EvalReport:
        """Run a FairnessAudit on the model and split for each sensitive column and return the per-group EvalReport.

        Args:
            model: TrainedModel reference to audit for bias.
            split: DataSplit whose test partition is used for per-group scoring.
            sensitive_columns: Non-empty sequence of protected attribute column names.

        Returns:
            EvalReport with parity_<column> metrics for every sensitive column.

        Raises:
            ValueError: If sensitive_columns is empty or contains invalid names.
        """
        column_tuple = tuple(sensitive_columns)
        if not column_tuple:
            raise ValueError("BiasDetector: sensitive_columns must be non-empty")
        for column in column_tuple:
            if not isinstance(column, str) or not column:
                raise ValueError(
                    "BiasDetector: every sensitive column name must be a non-empty string"
                )
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
                sensitive_columns=column_tuple,
                _config=KnotConfig(id="audit"),
            )
        inner_result = await self._run_inner(inner)
        return inner_result.outputs["audit"]
