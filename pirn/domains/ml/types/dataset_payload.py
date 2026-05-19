"""``DatasetPayload`` — DatasetManifest metadata bundled with MLFeatures."""

from __future__ import annotations

from pirn.core.payload import Payload
from pirn.domains.ml.types.dataset_manifest import DatasetManifest
from pirn.domains.ml.types.ml_features import MLFeatures


class DatasetPayload(Payload[DatasetManifest, MLFeatures]):
    @property
    def manifest(self) -> DatasetManifest:
        return self._metadata

    @property
    def features(self) -> MLFeatures:
        return self._data
