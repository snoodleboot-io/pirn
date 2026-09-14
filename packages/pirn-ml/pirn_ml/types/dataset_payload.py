"""``DatasetPayload`` — DatasetManifest metadata bundled with MLFeatures."""

from __future__ import annotations

from pirn.core.payload import Payload

from pirn_ml.types.dataset_manifest import DatasetManifest
from pirn_ml.types.ml_features import MLFeatures


class DatasetPayload(Payload[DatasetManifest, MLFeatures]):
    """``metadata`` is the :class:`DatasetManifest`; ``data`` is the ``MLFeatures``."""
