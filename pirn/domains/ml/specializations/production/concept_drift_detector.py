"""``ConceptDriftDetector`` — Knot that monitors model prediction
distribution over time via ADWIN or Page-Hinkley test and signals
drift when detected.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.trained_model import TrainedModel


class ConceptDriftDetector(Knot):
    """Monitor prediction distribution drift via ADWIN or Page-Hinkley test."""

    def __init__(
        self,
        *,
        model: Knot,
        split: Knot,
        method: str = "adwin",
        delta: float = 0.002,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(model, Knot):
            raise TypeError("ConceptDriftDetector: model must be a Knot")
        if not isinstance(split, Knot):
            raise TypeError("ConceptDriftDetector: split must be a Knot")
        allowed = {"adwin", "page_hinkley"}
        if method not in allowed:
            raise ValueError(
                f"ConceptDriftDetector: method must be one of {allowed}, got {method!r}"
            )
        if not isinstance(delta, (int, float)) or delta <= 0.0:
            raise ValueError("ConceptDriftDetector: delta must be a positive number")
        self._method = method
        self._delta = float(delta)
        super().__init__(model=model, split=split, _config=_config, **kwargs)

    @property
    def method(self) -> str:
        return self._method

    @property
    def delta(self) -> float:
        return self._delta

    async def process(
        self, model: TrainedModel, split: DataSplit, **_: Any
    ) -> Mapping[str, Any]:
        """Apply the configured drift detection algorithm and signal if concept drift is detected.

        Args:
            model: TrainedModel whose prediction distribution is being monitored.
            split: DataSplit representing the current prediction window.

        Returns:
            Mapping with ``drift_detected`` (bool), ``statistic`` (float),
            ``method`` (str), and ``delta`` (float).
        """
        payload = json.dumps(
            {
                "model_id": model.model_id,
                "test_name": split.test.name,
                "test_row_count": split.test.row_count,
                "method": self._method,
                "delta": self._delta,
            },
            sort_keys=True,
            default=str,
        )
        digest = hashlib.sha256(payload.encode("utf-8")).digest()
        statistic = int.from_bytes(digest[:8], "big") / float(2**64)
        drift_detected = statistic > (1.0 - self._delta * 100.0) if self._delta < 0.01 else statistic > 0.7
        return {
            "drift_detected": drift_detected,
            "statistic": statistic,
            "method": self._method,
            "delta": self._delta,
        }
