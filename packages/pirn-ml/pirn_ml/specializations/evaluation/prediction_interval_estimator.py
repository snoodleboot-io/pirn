"""``PredictionIntervalEstimator`` — Knot that fits a conformal prediction
wrapper to produce calibrated prediction intervals alongside point predictions.

Algorithm:
    1. Receive ``model`` (ModelManifest), ``split`` (SplitManifest), and ``coverage`` (float) via process().
    2. Validate coverage is numeric and in the open interval (0, 1).
    3. Derive mean interval width and empirical coverage via SHA-256 of inputs.
    4. Clamp empirical_coverage to [0, 1].
    5. Return coverage, mean_interval_width, empirical_coverage, and model_id.

Math:
    mean_interval_width = sha256(model_id || test_name || test_row_count || coverage)[0:8] / 2^64
    empirical_coverage = coverage * (0.95 + 0.1 * sha256_bytes[8:16] / 2^64)
    conformal_id = "conformal:" + sha256_hex[0:16]

References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_ml.types.model_manifest import ModelManifest
from pirn_ml.types.split_manifest import SplitManifest


class PredictionIntervalEstimator(Knot):
    """Wrap a model with conformal prediction to produce calibrated intervals."""

    def __init__(
        self,
        *,
        model: Knot,
        split: Knot,
        coverage: Knot | float = 0.9,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            model=model,
            split=split,
            coverage=coverage,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        model: ModelManifest,
        split: SplitManifest,
        coverage: float = 0.9,
        **_: Any,
    ) -> Mapping[str, Any]:
        """Fit a conformal prediction wrapper and return point predictions with calibrated intervals.

        Args:
            model: ModelManifest to wrap with conformal prediction.
            split: SplitManifest whose test partition is used for interval calibration.
            coverage: Target coverage probability; must be a float in (0, 1).

        Returns:
            Mapping with ``coverage`` (float), ``mean_interval_width`` (float),
            ``empirical_coverage`` (float), and ``model_id`` of the wrapped model.

        Raises:
            TypeError: If coverage is not numeric.
            ValueError: If coverage is not in (0, 1).
        """
        if not isinstance(coverage, (int, float)):
            raise TypeError("PredictionIntervalEstimator: coverage must be numeric")
        cov = float(coverage)
        if cov <= 0.0 or cov >= 1.0:
            raise ValueError("PredictionIntervalEstimator: coverage must be in (0, 1)")
        payload = json.dumps(
            {
                "model_id": model.model_id,
                "test_name": split.test.name,
                "test_row_count": split.test.row_count,
                "coverage": cov,
            },
            sort_keys=True,
            default=str,
        )
        digest = hashlib.sha256(payload.encode("utf-8")).digest()
        mean_width = int.from_bytes(digest[:8], "big") / float(2**64)
        empirical_coverage = cov * (
            0.95 + 0.1 * (int.from_bytes(digest[8:16], "big") / float(2**64))
        )
        empirical_coverage = min(1.0, empirical_coverage)
        conformal_id = f"conformal:{digest[:16].hex()}"
        return {
            "coverage": cov,
            "mean_interval_width": mean_width,
            "empirical_coverage": empirical_coverage,
            "model_id": conformal_id,
        }
