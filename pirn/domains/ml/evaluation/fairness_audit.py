"""``FairnessAudit`` — per-group metric audit (demographic parity / equal
opportunity).

The base implementation produces a deterministic
:class:`EvalMetadata` whose ``metrics`` map carries one entry per
sensitive column (the ``parity_<column>`` value) and whose ``details``
map records per-group placeholder counts. Concrete subclasses override
:meth:`process` to plug in a real per-group fit/predict/score loop.

Algorithm:
    1. Receive ``model`` (ModelManifest), ``split`` (SplitManifest), and
       ``sensitive_columns`` (sequence of str) via process().
    2. Validate that sensitive_columns is non-empty and all elements are non-empty strings.
    3. For each sensitive column, compute a deterministic parity score.
    4. Return an EvalMetadata with ``parity_<column>`` metrics.

Math:
    parity[col] = sha256(model_id || col || test_name || test_row_count)[0:8] as uint64 / 2^64

References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.types.eval_metadata import EvalMetadata
from pirn.domains.ml.types.eval_metrics import EvalMetrics
from pirn.domains.ml.types.eval_report_payload import EvalReportPayload
from pirn.domains.ml.types.model_manifest import ModelManifest
from pirn.domains.ml.types.split_manifest import SplitManifest


class FairnessAudit(Knot):
    """Per-group metric audit on the test partition."""

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
        model: ModelManifest,
        split: SplitManifest,
        sensitive_columns: Sequence[str] = (),
        **_: Any,
    ) -> EvalReportPayload:
        """Compute per-group parity scores for each sensitive column and return an EvalReportPayload.

        Args:
            model: ModelManifest reference to audit.
            split: SplitManifest whose test partition is used for per-group scoring.
            sensitive_columns: Non-empty sequence of sensitive column name strings.

        Returns:
            EvalReportPayload with parity_<column> metrics for every sensitive column.

        Raises:
            ValueError: If sensitive_columns is empty or any element is not a non-empty string.
        """
        column_tuple = tuple(sensitive_columns)
        if not column_tuple:
            raise ValueError("FairnessAudit: sensitive_columns must be non-empty")
        for column in column_tuple:
            if not isinstance(column, str) or not column:
                raise ValueError(
                    "FairnessAudit: every sensitive column name must be a non-empty string"
                )
        parity_scores: dict[str, float] = {}
        details: dict[str, Any] = {
            "model_id": model.model_id,
            "test_row_count": split.test.row_count,
            "sensitive_columns": list(column_tuple),
        }
        for column in column_tuple:
            parity_scores[f"parity_{column}"] = self._parity_score(model, split, column)
        return EvalReportPayload(
            metadata=EvalMetadata(
                model_id=model.model_id,
                dataset_name=split.test.name,
                evaluated_at=datetime.now(UTC),
            ),
            data=EvalMetrics(
                scores=MappingProxyType(parity_scores),
                details=MappingProxyType(details),
            ),
        )

    def _parity_score(self, model: ModelManifest, split: SplitManifest, column: str) -> float:
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
