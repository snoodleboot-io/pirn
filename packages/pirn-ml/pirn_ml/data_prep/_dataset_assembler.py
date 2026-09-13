"""``_DatasetAssembler`` — convert a raw :class:`DataBatch` into a :class:`DatasetPayload`.

Terminal knot of the :class:`~pirn_ml.data_prep.dataset_loader.DatasetLoader`
inner tapestry. Extracts the feature matrix ``X`` and optional target vector
``y`` from the batch rows using the declared column names.

Algorithm:
    1. Receive ``batch`` (DataBatch), ``name``, ``feature_names``, and
       ``target_name`` via process().
    2. Validate name and feature_names are non-empty.
    3. For an empty batch, produce empty float arrays of the right shape.
    4. Otherwise extract each row's feature columns into a 2D array
       (falling back to an object array when values are not uniformly
       numeric), and, if configured, the target column into a 1D array.
    5. Build a DatasetManifest recording name, columns, row count, source
       URI, and fetch time.
    6. Return a DatasetPayload wrapping the manifest and the MLFeatures.

References:
    pirn_data/data_batch.py
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

import numpy as np
from pirn.core.assembler import Assembler
from pirn_data.data_batch import DataBatch

from pirn_ml.types.dataset_manifest import DatasetManifest
from pirn_ml.types.dataset_payload import DatasetPayload
from pirn_ml.types.ml_features import MLFeatures


class _DatasetAssembler(Assembler):
    """Convert a raw :class:`DataBatch` into a typed :class:`DatasetPayload`.

    Terminal knot of the :class:`DatasetLoader` inner tapestry. Extracts
    the feature matrix ``X`` and optional target vector ``y`` from the batch
    rows using the declared column names.
    """

    async def process(
        self,
        batch: DataBatch,
        name: str,
        feature_names: Sequence[str],
        target_name: str | None = None,
        **_: Any,
    ) -> DatasetPayload:
        if not name:
            raise ValueError("DatasetLoader: name must be a non-empty string")
        if not feature_names:
            raise ValueError("DatasetLoader: feature_names must be non-empty")

        rows = batch.rows
        if not rows:
            feature_matrix = np.empty((0, len(feature_names)), dtype=float)
            target_vector: np.ndarray | None = np.empty(0, dtype=float) if target_name else None
        else:
            try:
                raw_features = [[row[col] for col in feature_names] for row in rows]
            except (KeyError, TypeError) as exc:
                raise ValueError(
                    f"DatasetLoader: could not extract features from batch: {exc}"
                ) from exc
            try:
                feature_matrix = np.array(raw_features, dtype=float)
            except (TypeError, ValueError):
                feature_matrix = np.array(raw_features, dtype=object)
            target_vector = None
            if target_name:
                try:
                    raw_targets = [row[target_name] for row in rows]
                except (KeyError, TypeError) as exc:
                    raise ValueError(
                        f"DatasetLoader: could not extract target '{target_name}': {exc}"
                    ) from exc
                try:
                    target_vector = np.array([float(v) for v in raw_targets], dtype=float)
                except (TypeError, ValueError):
                    target_vector = np.array(raw_targets, dtype=object)

        manifest = DatasetManifest(
            name=name,
            feature_names=tuple(feature_names),
            target_name=target_name,
            row_count=int(feature_matrix.shape[0]),
            source_uri=batch.source_uri,
            fetched_at=datetime.now(UTC),
        )
        return DatasetPayload(
            metadata=manifest,
            data=MLFeatures(feature_matrix=feature_matrix, target_vector=target_vector),
        )
