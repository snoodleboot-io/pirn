"""``CalibrationFitter`` — Knot that fits a Platt scaling or isotonic
regression calibrator on held-out probabilities and returns the calibrated
model reference.

Algorithm:
    1. Receive ``model`` (ModelManifest), ``split`` (SplitManifest), and ``method`` (str) via process().
    2. Validate method is one of {"platt", "isotonic"}.
    3. Derive a deterministic calibrated model_id via SHA-256(model_id + method + test metadata).
    4. Return a ModelManifest with algorithm "calibrated_<method>".

Math:
    calibrated_id = "calibrated:" + sha256(model_id || method || test_name || test_row_count)[0:16]

References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

import hashlib
import json
from types import MappingProxyType
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.types.model_manifest import ModelManifest
from pirn.domains.ml.types.split_manifest import SplitManifest


class CalibrationFitter(Knot):
    """Fit a calibration wrapper on a model using held-out probability estimates."""

    def __init__(
        self,
        *,
        model: Knot,
        split: Knot,
        method: Knot | str = "platt",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            model=model,
            split=split,
            method=method,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        model: ModelManifest,
        split: SplitManifest,
        method: str = "platt",
        **_: Any,
    ) -> ModelManifest:
        """Fit a calibration layer on the held-out split and return a calibrated ModelManifest.

        Args:
            model: ModelManifest whose raw probability outputs will be calibrated.
            split: SplitManifest whose test partition is used as the calibration hold-out set.
            method: Calibration method; must be one of {"platt", "isotonic"}.

        Returns:
            ModelManifest with algorithm ``"calibrated_<method>"`` wrapping the
            original model, carrying calibration metadata in hyperparameters.

        Raises:
            ValueError: If method is not a valid calibration method.
        """
        allowed = {"platt", "isotonic"}
        if method not in allowed:
            raise ValueError(f"CalibrationFitter: method must be one of {allowed}, got {method!r}")
        payload = json.dumps(
            {
                "model_id": model.model_id,
                "method": method,
                "test_name": split.test.name,
                "test_row_count": split.test.row_count,
            },
            sort_keys=True,
            default=str,
        )
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        calibrated_id = f"calibrated:{digest[:16]}"
        return ModelManifest(
            model_id=calibrated_id,
            algorithm=f"calibrated_{method}",
            hyperparameters=MappingProxyType(
                {
                    "base_model_id": model.model_id,
                    "calibration_method": method,
                    "calibration_samples": split.test.row_count,
                }
            ),
            feature_names=model.feature_names,
            target_name=model.target_name,
        )
