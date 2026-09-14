"""``TrainedModelPayload`` — ModelManifest metadata bundled with FittedEstimator."""

from __future__ import annotations

from pirn.core.payload import Payload

from pirn_ml.types.fitted_estimator import FittedEstimator
from pirn_ml.types.model_manifest import ModelManifest


class TrainedModelPayload(Payload[ModelManifest, FittedEstimator]):
    """``metadata`` is the :class:`ModelManifest`; ``data`` is the ``FittedEstimator``."""
