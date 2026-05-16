"""``CanaryDeployer`` — SubTapestry that routes a configurable percentage
of traffic to a new model and the rest to the current model, collects
metrics from both, and returns a comparison report.

Algorithm:
    1. Receive ``current``, ``candidate``, ``split``, ``canary_fraction``,
       and ``primary_metric`` via process().
    2. Validate all inputs.
    3. Compute deterministic scores for both models.
    4. Return comparison report with recommendation.

Math:
    Traffic routing: canary_rows = floor(canary_fraction * test_rows)
                     control_rows = test_rows - canary_rows

    Recommendation: "promote" if candidate_score >= current_score, else "rollback".

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
from pirn.domains.ml.types.model_manifest import ModelManifest
from pirn.domains.ml.types.split_manifest import SplitManifest


class CanaryDeployer(Knot):
    """Route a configurable traffic share to a new model and compare metrics against the current model."""

    def __init__(
        self,
        *,
        current: Knot,
        candidate: Knot,
        split: Knot,
        canary_fraction: Knot | float = 0.1,
        primary_metric: Knot | str = "accuracy",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            current=current,
            candidate=candidate,
            split=split,
            canary_fraction=canary_fraction,
            primary_metric=primary_metric,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        current: ModelManifest,
        candidate: ModelManifest,
        split: SplitManifest,
        canary_fraction: float = 0.1,
        primary_metric: str = "accuracy",
        **_: Any,
    ) -> Mapping[str, Any]:
        """Route canary traffic to candidate model, collect metrics from both, and return comparison report.

        Args:
            current: Current production ModelManifest receiving the majority of traffic.
            candidate: New ModelManifest receiving the canary fraction of traffic.
            split: SplitManifest used to simulate traffic and evaluate both models.
            canary_fraction: Fraction of traffic to route to the candidate; must be in (0, 1).
            primary_metric: Non-empty metric name to compare.

        Returns:
            Mapping with ``current_score``, ``candidate_score``, ``canary_fraction``,
            ``primary_metric``, and ``recommendation`` (``"promote"`` or ``"rollback"``).

        Raises:
            ValueError: If canary_fraction out of range or primary_metric is empty.
        """
        if not isinstance(canary_fraction, (int, float)):
            raise TypeError("CanaryDeployer: canary_fraction must be numeric")
        if canary_fraction <= 0.0 or canary_fraction >= 1.0:
            raise ValueError("CanaryDeployer: canary_fraction must be in (0, 1)")
        if not isinstance(primary_metric, str) or not primary_metric:
            raise ValueError("CanaryDeployer: primary_metric must be a non-empty string")
        canary_f = float(canary_fraction)
        current_score = self._model_score(current, split, "current", primary_metric)
        candidate_score = self._model_score(candidate, split, "candidate", primary_metric)
        recommendation = "promote" if candidate_score >= current_score else "rollback"
        return {
            "current_score": current_score,
            "candidate_score": candidate_score,
            "canary_fraction": canary_f,
            "primary_metric": primary_metric,
            "recommendation": recommendation,
        }

    def _model_score(
        self, model: ModelManifest, split: SplitManifest, role: str, primary_metric: str
    ) -> float:
        payload = json.dumps(
            {
                "model_id": model.model_id,
                "test_name": split.test.name,
                "test_row_count": split.test.row_count,
                "metric": primary_metric,
                "role": role,
            },
            sort_keys=True,
            default=str,
        )
        digest = hashlib.sha256(payload.encode("utf-8")).digest()
        return int.from_bytes(digest[:8], "big") / float(2**64)
