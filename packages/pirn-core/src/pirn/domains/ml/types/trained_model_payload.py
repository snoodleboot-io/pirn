"""``TrainedModelPayload`` — ModelManifest metadata bundled with FittedEstimator."""

from __future__ import annotations

from pirn.core.payload import Payload
from pirn.domains.ml.types.fitted_estimator import FittedEstimator
from pirn.domains.ml.types.model_manifest import ModelManifest


class TrainedModelPayload(Payload[ModelManifest, FittedEstimator]):
    @property
    def manifest(self) -> ModelManifest:
        return self._metadata

    @property
    def estimator(self) -> FittedEstimator:
        return self._data
