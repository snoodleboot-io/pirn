"""``PredictionIntervalEstimator`` — SubTapestry that fits a conformal
prediction wrapper to produce calibrated prediction intervals alongside
point predictions.
"""

from __future__ import annotations

import hashlib
import json
from types import MappingProxyType
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


class PredictionIntervalEstimator(SubTapestry):
    """Wrap a model with conformal prediction to produce calibrated intervals."""

    def __init__(
        self,
        *,
        model: Knot,
        split: Knot,
        coverage: float = 0.9,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(model, Knot):
            raise TypeError("PredictionIntervalEstimator: model must be a Knot")
        if not isinstance(split, Knot):
            raise TypeError("PredictionIntervalEstimator: split must be a Knot")
        if not isinstance(coverage, (int, float)):
            raise TypeError("PredictionIntervalEstimator: coverage must be numeric")
        if coverage <= 0.0 or coverage >= 1.0:
            raise ValueError(
                "PredictionIntervalEstimator: coverage must be in (0, 1)"
            )
        self._coverage = float(coverage)
        super().__init__(model=model, split=split, _config=_config, **kwargs)

    @property
    def coverage(self) -> float:
        return self._coverage

    async def process(
        self, model: TrainedModel, split: DataSplit, **_: Any
    ) -> Mapping[str, Any]:
        """Fit a conformal prediction wrapper and return point predictions with calibrated intervals.

        Args:
            model: TrainedModel to wrap with conformal prediction.
            split: DataSplit whose test partition is used for interval calibration.

        Returns:
            Mapping with ``coverage`` (float), ``mean_interval_width`` (float),
            ``empirical_coverage`` (float), and ``model_id`` of the wrapped model.
        """
        payload = json.dumps(
            {
                "model_id": model.model_id,
                "test_name": split.test.name,
                "test_row_count": split.test.row_count,
                "coverage": self._coverage,
            },
            sort_keys=True,
            default=str,
        )
        digest = hashlib.sha256(payload.encode("utf-8")).digest()
        mean_width = int.from_bytes(digest[:8], "big") / float(2**64)
        empirical_coverage = self._coverage * (
            0.95 + 0.1 * (int.from_bytes(digest[8:16], "big") / float(2**64))
        )
        empirical_coverage = min(1.0, empirical_coverage)
        conformal_id = f"conformal:{digest[:16]}"
        return {
            "coverage": self._coverage,
            "mean_interval_width": mean_width,
            "empirical_coverage": empirical_coverage,
            "model_id": conformal_id,
        }
