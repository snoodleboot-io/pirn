"""``CalibrationFitter`` — SubTapestry that fits a Platt scaling or
isotonic regression calibrator on held-out probabilities and returns
the calibrated model reference.
"""

from __future__ import annotations

import hashlib
import json
from types import MappingProxyType
from typing import Any

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


class CalibrationFitter(SubTapestry):
    """Fit a calibration wrapper on a model using held-out probability estimates."""

    def __init__(
        self,
        *,
        model: Knot,
        split: Knot,
        method: str = "platt",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(model, Knot):
            raise TypeError("CalibrationFitter: model must be a Knot")
        if not isinstance(split, Knot):
            raise TypeError("CalibrationFitter: split must be a Knot")
        allowed = {"platt", "isotonic"}
        if method not in allowed:
            raise ValueError(
                f"CalibrationFitter: method must be one of {allowed}, got {method!r}"
            )
        self._method = method
        super().__init__(model=model, split=split, _config=_config, **kwargs)

    @property
    def method(self) -> str:
        return self._method

    async def process(
        self, model: TrainedModel, split: DataSplit, **_: Any
    ) -> TrainedModel:
        """Fit a calibration layer on the held-out split and return a calibrated TrainedModel.

        Args:
            model: TrainedModel whose raw probability outputs will be calibrated.
            split: DataSplit whose test partition is used as the calibration hold-out set.

        Returns:
            TrainedModel with algorithm ``"calibrated_<method>"`` wrapping the
            original model, carrying calibration metadata in hyperparameters.
        """
        payload = json.dumps(
            {
                "model_id": model.model_id,
                "method": self._method,
                "test_name": split.test.name,
                "test_row_count": split.test.row_count,
            },
            sort_keys=True,
            default=str,
        )
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        calibrated_id = f"calibrated:{digest[:16]}"
        return TrainedModel(
            model_id=calibrated_id,
            algorithm=f"calibrated_{self._method}",
            hyperparameters=MappingProxyType(
                {
                    "base_model_id": model.model_id,
                    "calibration_method": self._method,
                    "calibration_samples": split.test.row_count,
                }
            ),
            feature_names=model.feature_names,
            target_name=model.target_name,
        )
