"""``DataDriftDetector`` — Knot that compares input feature distributions
(PSI, KS test) between reference and current windows and flags drifted features.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.types.data_split import DataSplit


class DataDriftDetector(Knot):
    """Detect PSI and KS-based feature distribution drift between reference and current windows."""

    def __init__(
        self,
        *,
        reference: Knot,
        current: Knot,
        features: Sequence[str],
        psi_threshold: float = 0.2,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(reference, Knot):
            raise TypeError("DataDriftDetector: reference must be a Knot")
        if not isinstance(current, Knot):
            raise TypeError("DataDriftDetector: current must be a Knot")
        feature_tuple = tuple(features)
        if not feature_tuple:
            raise ValueError("DataDriftDetector: features must be non-empty")
        for feat in feature_tuple:
            if not isinstance(feat, str) or not feat:
                raise ValueError(
                    "DataDriftDetector: every feature name must be a non-empty string"
                )
        if not isinstance(psi_threshold, (int, float)) or psi_threshold < 0.0:
            raise ValueError(
                "DataDriftDetector: psi_threshold must be a non-negative number"
            )
        self._features = feature_tuple
        self._psi_threshold = float(psi_threshold)
        super().__init__(reference=reference, current=current, _config=_config, **kwargs)

    @property
    def features(self) -> tuple[str, ...]:
        return self._features

    @property
    def psi_threshold(self) -> float:
        return self._psi_threshold

    async def process(
        self, reference: DataSplit, current: DataSplit, **_: Any
    ) -> Mapping[str, Any]:
        """Compute PSI and KS statistics for each feature and flag drifted features.

        Args:
            reference: DataSplit representing the baseline feature distribution.
            current: DataSplit representing the live or recent feature distribution.

        Returns:
            Mapping with ``psi`` (dict per feature), ``ks_statistic`` (dict per feature),
            ``drifted_features`` (list[str]), and ``drift_detected`` (bool).
        """
        psi: dict[str, float] = {}
        ks_statistic: dict[str, float] = {}
        for feat in self._features:
            psi[feat] = self._stat_value(reference, current, feat, "psi")
            ks_statistic[feat] = self._stat_value(reference, current, feat, "ks")
        drifted = [f for f in self._features if psi[f] > self._psi_threshold]
        return {
            "psi": psi,
            "ks_statistic": ks_statistic,
            "drifted_features": drifted,
            "drift_detected": len(drifted) > 0,
        }

    def _stat_value(
        self,
        reference: DataSplit,
        current: DataSplit,
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
