"""``CanaryDeployer`` — SubTapestry that routes a configurable percentage
of traffic to a new model and the rest to the current model, collects
metrics from both, and returns a comparison report.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.trained_model import TrainedModel
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


@knot
async def _emit_value(value: Any) -> Any:
    return value


class CanaryDeployer(SubTapestry):
    """Route a configurable traffic share to a new model and compare metrics against the current model."""

    def __init__(
        self,
        *,
        current: Knot,
        candidate: Knot,
        split: Knot,
        canary_fraction: float = 0.1,
        primary_metric: str = "accuracy",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(current, Knot):
            raise TypeError("CanaryDeployer: current must be a Knot")
        if not isinstance(candidate, Knot):
            raise TypeError("CanaryDeployer: candidate must be a Knot")
        if not isinstance(split, Knot):
            raise TypeError("CanaryDeployer: split must be a Knot")
        if not isinstance(canary_fraction, (int, float)):
            raise TypeError("CanaryDeployer: canary_fraction must be numeric")
        if canary_fraction <= 0.0 or canary_fraction >= 1.0:
            raise ValueError(
                "CanaryDeployer: canary_fraction must be in (0, 1)"
            )
        if not isinstance(primary_metric, str) or not primary_metric:
            raise ValueError(
                "CanaryDeployer: primary_metric must be a non-empty string"
            )
        self._canary_fraction = float(canary_fraction)
        self._primary_metric = primary_metric
        super().__init__(current=current, candidate=candidate, split=split, _config=_config, **kwargs)

    @property
    def canary_fraction(self) -> float:
        return self._canary_fraction

    @property
    def primary_metric(self) -> str:
        return self._primary_metric

    async def process(
        self,
        current: TrainedModel,
        candidate: TrainedModel,
        split: DataSplit,
        **_: Any,
    ) -> Mapping[str, Any]:
        """Route canary traffic to candidate model, collect metrics from both, and return comparison report.

        Args:
            current: Current production TrainedModel receiving the majority of traffic.
            candidate: New TrainedModel receiving the canary fraction of traffic.
            split: DataSplit used to simulate traffic and evaluate both models.

        Returns:
            Mapping with ``current_score``, ``candidate_score``, ``canary_fraction``,
            ``primary_metric``, and ``recommendation`` (``"promote"`` or ``"rollback"``).
        """
        current_score = self._model_score(current, split, "current")
        candidate_score = self._model_score(candidate, split, "candidate")
        recommendation = "promote" if candidate_score >= current_score else "rollback"
        return {
            "current_score": current_score,
            "candidate_score": candidate_score,
            "canary_fraction": self._canary_fraction,
            "primary_metric": self._primary_metric,
            "recommendation": recommendation,
        }

    def _model_score(
        self, model: TrainedModel, split: DataSplit, role: str
    ) -> float:
        payload = json.dumps(
            {
                "model_id": model.model_id,
                "test_name": split.test.name,
                "test_row_count": split.test.row_count,
                "metric": self._primary_metric,
                "role": role,
            },
            sort_keys=True,
            default=str,
        )
        digest = hashlib.sha256(payload.encode("utf-8")).digest()
        return int.from_bytes(digest[:8], "big") / float(2**64)
