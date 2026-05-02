"""``FairnessAudit`` — per-group metric audit (demographic parity / equal
opportunity).

The base implementation produces a deterministic
:class:`EvalReport` whose ``metrics`` map carries one entry per
sensitive column (the ``parity_<column>`` value) and whose ``details``
map records per-group placeholder counts. Concrete subclasses override
:meth:`process` to plug in a real per-group fit/predict/score loop.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.eval_report import EvalReport
from pirn.domains.ml.types.trained_model import TrainedModel


class FairnessAudit(Knot):
    """Per-group metric audit on the test partition."""

    def __init__(
        self,
        *,
        model: Knot,
        split: Knot,
        sensitive_columns: Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        column_tuple = tuple(sensitive_columns)
        if not column_tuple:
            raise ValueError(
                "FairnessAudit: sensitive_columns must be non-empty"
            )
        for column in column_tuple:
            if not isinstance(column, str) or not column:
                raise ValueError(
                    "FairnessAudit: every sensitive column name must be a "
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
        metrics: dict[str, float] = {}
        details: dict[str, Any] = {
            "model_id": model.model_id,
            "test_row_count": split.test.row_count,
            "sensitive_columns": list(self._sensitive_columns),
        }
        for column in self._sensitive_columns:
            metrics[f"parity_{column}"] = self._parity_score(model, split, column)
        return EvalReport(
            model_id=model.model_id,
            metrics=MappingProxyType(metrics),
            dataset_name=split.test.name,
            evaluated_at=datetime.now(timezone.utc),
            details=MappingProxyType(details),
        )

    def _parity_score(
        self, model: TrainedModel, split: DataSplit, column: str
    ) -> float:
        payload = json.dumps(
            {
                "model_id": model.model_id,
                "column": column,
                "test_name": split.test.name,
                "test_row_count": split.test.row_count,
            },
            sort_keys=True,
            default=str,
        )
        digest = hashlib.sha256(payload.encode("utf-8")).digest()
        return int.from_bytes(digest[:8], "big") / float(2**64)
