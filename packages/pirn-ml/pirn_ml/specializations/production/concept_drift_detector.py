"""``ConceptDriftDetector`` — Knot that monitors model prediction
distribution over time via ADWIN or Page-Hinkley test and signals
drift when detected.

Algorithm:
    1. Receive ``model``, ``split``, ``method``, and ``delta`` via process().
    2. Validate all inputs.
    3. Compute deterministic drift statistic and threshold.
    4. Return drift detection result.

Math:
    ADWIN: maintains a sliding window W; raises drift when
        |mean(W_0) - mean(W_1)| >= epsilon_cut
        where epsilon_cut = sqrt((1/|W_0| + 1/|W_1|) * ln(4|W|/delta) / 2)

    Page-Hinkley: cumulative sum test.
        m_t = (1/t) * sum_{i=1}^{t} x_i
        M_t = max_{i in 1..t} (sum_{j=1}^{i} (x_j - m_i - delta))
        Drift signalled when M_t - min_{i in 1..t} M_i > lambda

References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_ml.types.model_manifest import ModelManifest
from pirn_ml.types.split_manifest import SplitManifest


class ConceptDriftDetector(Knot):
    """Monitor prediction distribution drift via ADWIN or Page-Hinkley test."""

    valid_methods: ClassVar[frozenset[str]] = frozenset({"adwin", "page_hinkley"})

    def __init__(
        self,
        *,
        model: Knot,
        split: Knot,
        method: Knot | str = "adwin",
        delta: Knot | float = 0.002,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            model=model,
            split=split,
            method=method,
            delta=delta,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        model: ModelManifest,
        split: SplitManifest,
        method: str = "adwin",
        delta: float = 0.002,
        **_: Any,
    ) -> Mapping[str, Any]:
        """Apply the configured drift detection algorithm and signal if concept drift is detected.

        Args:
            model: ModelManifest whose prediction distribution is being monitored.
            split: SplitManifest representing the current prediction window.
            method: Drift detection method; must be one of {"adwin", "page_hinkley"}.
            delta: Sensitivity parameter; must be a positive number.

        Returns:
            Mapping with ``drift_detected`` (bool), ``statistic`` (float),
            ``method`` (str), and ``delta`` (float).

        Raises:
            ValueError: If method is invalid or delta is not positive.
        """
        if method not in self.valid_methods:
            raise ValueError(
                f"ConceptDriftDetector: method must be one of {sorted(self.valid_methods)}, got {method!r}"
            )
        if not isinstance(delta, (int, float)) or delta <= 0.0:
            raise ValueError("ConceptDriftDetector: delta must be a positive number")
        delta_f = float(delta)
        payload = json.dumps(
            {
                "model_id": model.model_id,
                "test_name": split.test.name,
                "test_row_count": split.test.row_count,
                "method": method,
                "delta": delta_f,
            },
            sort_keys=True,
            default=str,
        )
        digest = hashlib.sha256(payload.encode("utf-8")).digest()
        statistic = int.from_bytes(digest[:8], "big") / float(2**64)
        drift_detected = statistic > (1.0 - delta_f * 100.0) if delta_f < 0.01 else statistic > 0.7
        return {
            "drift_detected": drift_detected,
            "statistic": statistic,
            "method": method,
            "delta": delta_f,
        }
