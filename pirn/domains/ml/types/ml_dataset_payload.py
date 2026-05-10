"""``DatasetPayload`` — DatasetManifest metadata bundled with feature/target arrays.

.. deprecated::
    Import :class:`pirn.domains.ml.types.dataset_payload.DatasetPayload` instead.
    This module is retained for backwards compatibility only.
"""

from __future__ import annotations

import numpy as np

from pirn.core.payload import Payload
from pirn.domains.ml.types.ml_dataset import DatasetManifest


class DatasetPayload(Payload[DatasetManifest, dict[str, np.ndarray]]):
    """ML dataset: metadata + {"X": feature_matrix, "y": target_vector}."""

    @property
    def dataset(self) -> DatasetManifest:
        return self._metadata

    @property
    def arrays(self) -> dict[str, np.ndarray]:
        return self._data
