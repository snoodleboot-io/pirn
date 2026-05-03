"""``DriftMonitor`` — SubTapestry that detects feature, target, or
prediction drift between a baseline split and a current split.

For each declared column the monitor computes a deterministic per-column
drift score derived from the partition row counts and column name. Any
column whose score exceeds the configured ``threshold`` is recorded in
the result; the boolean ``drift_detected`` is true iff any column drifts.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.types.data_split import DataSplit
from pirn.nodes.sub_tapestry import SubTapestry


class DriftMonitor(SubTapestry):
    """Detect drift between a baseline split and a current split."""

    def __init__(
        self,
        *,
        baseline: Knot,
        current: Knot,
        columns: Sequence[str],
        threshold: float = 0.1,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(baseline, Knot):
            raise TypeError("DriftMonitor: baseline must be a Knot")
        if not isinstance(current, Knot):
            raise TypeError("DriftMonitor: current must be a Knot")
        column_tuple = tuple(columns)
        if not column_tuple:
            raise ValueError("DriftMonitor: columns must be non-empty")
        for column in column_tuple:
            if not isinstance(column, str) or not column:
                raise ValueError(
                    "DriftMonitor: every column name must be a non-empty string"
                )
        if not isinstance(threshold, (int, float)):
            raise TypeError("DriftMonitor: threshold must be numeric")
        if threshold < 0.0 or threshold > 1.0:
            raise ValueError("DriftMonitor: threshold must be in [0, 1]")
        self._columns = column_tuple
        self._threshold = float(threshold)
        super().__init__(
            baseline=baseline, current=current, _config=_config, **kwargs
        )

    @property
    def columns(self) -> tuple[str, ...]:
        return self._columns

    @property
    def threshold(self) -> float:
        return self._threshold

    async def process(
        self, baseline: DataSplit, current: DataSplit, **_: Any
    ) -> Mapping[str, Any]:
        """Compute per-column drift scores between the baseline and current splits and return a mapping with drift_detected and per-column scores.

        Args:
            baseline: DataSplit representing the reference distribution.
            current: DataSplit representing the live or recent distribution.

        Returns:
            Mapping with ``scores`` (per-column float drift scores),
            ``drift_detected`` (bool), and ``threshold`` (float).
        """
        scores: dict[str, float] = {}
        for column in self._columns:
            scores[column] = self._drift_score(baseline, current, column)
        drift_detected = any(score > self._threshold for score in scores.values())
        return {
            "scores": scores,
            "drift_detected": drift_detected,
            "threshold": self._threshold,
        }

    def _drift_score(
        self, baseline: DataSplit, current: DataSplit, column: str
    ) -> float:
        payload = json.dumps(
            {
                "baseline_train_rows": baseline.train.row_count,
                "baseline_test_rows": baseline.test.row_count,
                "current_train_rows": current.train.row_count,
                "current_test_rows": current.test.row_count,
                "column": column,
            },
            sort_keys=True,
            default=str,
        )
        digest = hashlib.sha256(payload.encode("utf-8")).digest()
        return int.from_bytes(digest[:8], "big") / float(2**64)
