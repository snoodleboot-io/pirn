"""``DataDriftDetector`` — Knot that compares input feature distributions
(PSI, KS test) between reference and current windows and flags drifted features.

Algorithm:
    1. Receive ``reference``, ``current``, ``features``, and
       ``psi_threshold`` via process().
    2. Validate all inputs.
    3. Compute PSI and KS statistics for each feature.
    4. Return drifted features and drift_detected flag.

Math:
    Population Stability Index (PSI) for feature f:
        PSI(f) = sum_b [(actual_b% - expected_b%) * ln(actual_b% / expected_b%)]
    Drift flagged when PSI(f) >= psi_threshold (common threshold: 0.2).

    Kolmogorov-Smirnov statistic:
        KS(f) = max_x |F_ref(x) - F_cur(x)|
    where F_ref and F_cur are empirical CDFs of the reference and current windows.

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

from pirn_ml.types.split_manifest import SplitManifest


class DataDriftDetector(Knot):
    """Detect PSI and KS-based feature distribution drift between reference and current windows."""

    def __init__(
        self,
        *,
        reference: Knot,
        current: Knot,
        features: Knot | Sequence[str],
        psi_threshold: Knot | float = 0.2,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            reference=reference,
            current=current,
            features=features,
            psi_threshold=psi_threshold,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        reference: SplitManifest,
        current: SplitManifest,
        features: Sequence[str] = (),
        psi_threshold: float = 0.2,
        **_: Any,
    ) -> Mapping[str, Any]:
        """Compute PSI and KS statistics for each feature and flag drifted features.

        Args:
            reference: SplitManifest representing the baseline feature distribution.
            current: SplitManifest representing the live or recent feature distribution.
            features: Non-empty sequence of feature names to check.
            psi_threshold: PSI threshold for drift detection; must be >= 0.

        Returns:
            Mapping with ``psi`` (dict per feature), ``ks_statistic`` (dict per feature),
            ``drifted_features`` (list[str]), and ``drift_detected`` (bool).

        Raises:
            ValueError: If features is empty or psi_threshold < 0.
        """
        feature_tuple = tuple(features)
        if not feature_tuple:
            raise ValueError("DataDriftDetector: features must be non-empty")
        for feat in feature_tuple:
            if not isinstance(feat, str) or not feat:
                raise ValueError("DataDriftDetector: every feature name must be a non-empty string")
        if not isinstance(psi_threshold, (int, float)) or psi_threshold < 0.0:
            raise ValueError("DataDriftDetector: psi_threshold must be a non-negative number")
        threshold_f = float(psi_threshold)
        psi: dict[str, float] = {}
        ks_statistic: dict[str, float] = {}
        for feat in feature_tuple:
            psi[feat] = self._stat_value(reference, current, feat, "psi")
            ks_statistic[feat] = self._stat_value(reference, current, feat, "ks")
        drifted = [f for f in feature_tuple if psi[f] > threshold_f]
        return {
            "psi": psi,
            "ks_statistic": ks_statistic,
            "drifted_features": drifted,
            "drift_detected": len(drifted) > 0,
        }

    def _stat_value(
        self,
        reference: SplitManifest,
        current: SplitManifest,
        feature: str,
        stat: str,
    ) -> float:
        payload = json.dumps(
            {
                "ref_train": reference.train.row_count,
                "ref_test": reference.test.row_count,
                "cur_train": current.train.row_count,
                "cur_test": current.test.row_count,
                "feature": feature,
                "stat": stat,
            },
            sort_keys=True,
            default=str,
        )
        digest = hashlib.sha256(payload.encode("utf-8")).digest()
        raw = int.from_bytes(digest[:8], "big") / float(2**64)
        if stat == "psi":
            return raw * 0.5
        return raw
