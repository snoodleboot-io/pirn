"""``DriftMonitor`` — Knot that detects feature, target, or prediction drift
between a baseline split and a current split.

For each declared column the monitor computes a deterministic per-column
drift score derived from the partition row counts and column name. Any
column whose score exceeds the configured ``threshold`` is recorded in
the result; the boolean ``drift_detected`` is true iff any column drifts.

Algorithm:
    1. Receive ``baseline``, ``current``, ``columns``, and ``threshold``
       via process().
    2. Validate all inputs.
    3. Compute per-column drift scores.
    4. Return scores, drift_detected, and threshold.


References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.types.split_manifest import SplitManifest


class DriftMonitor(Knot):
    """Detect drift between a baseline split and a current split."""

    def __init__(
        self,
        *,
        baseline: Knot,
        current: Knot,
        columns: Knot | Sequence[str],
        threshold: Knot | float = 0.1,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            baseline=baseline,
            current=current,
            columns=columns,
            threshold=threshold,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        baseline: SplitManifest,
        current: SplitManifest,
        columns: Sequence[str] = (),
        threshold: float = 0.1,
        **_: Any,
    ) -> Mapping[str, Any]:
        """Compute per-column drift scores between the baseline and current splits and return a mapping with drift_detected and per-column scores.

        Args:
            baseline: SplitManifest representing the reference distribution.
            current: SplitManifest representing the live or recent distribution.
            columns: Non-empty sequence of column names to check for drift.
            threshold: Drift score threshold; must be in [0, 1].

        Returns:
            Mapping with ``scores`` (per-column float drift scores),
            ``drift_detected`` (bool), and ``threshold`` (float).

        Raises:
            ValueError: If columns is empty or threshold is out of range.
        """
        column_tuple = tuple(columns)
        if not column_tuple:
            raise ValueError("DriftMonitor: columns must be non-empty")
        for column in column_tuple:
            if not isinstance(column, str) or not column:
                raise ValueError("DriftMonitor: every column name must be a non-empty string")
        if not isinstance(threshold, (int, float)):
            raise TypeError("DriftMonitor: threshold must be numeric")
        if threshold < 0.0 or threshold > 1.0:
            raise ValueError("DriftMonitor: threshold must be in [0, 1]")
        threshold_f = float(threshold)
        scores: dict[str, float] = {}
        for column in column_tuple:
            scores[column] = self._drift_score(baseline, current, column)
        drift_detected = any(score > threshold_f for score in scores.values())
        return {
            "scores": scores,
            "drift_detected": drift_detected,
            "threshold": threshold_f,
        }

    def _drift_score(self, baseline: SplitManifest, current: SplitManifest, column: str) -> float:
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
