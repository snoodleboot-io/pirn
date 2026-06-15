"""``Trainer`` — train one model on a :class:`SplitManifest.train` slice.

At this orchestration layer the knot does not actually fit a model; it
emits a deterministic :class:`ModelManifest` reference whose ``model_id``
hashes the algorithm + hyperparameters + train-split metadata. Concrete
subclasses (e.g. ``SklearnTrainer``) override :meth:`process` to perform
the actual fit using the upstream data and return a real artifact id.

Algorithm:
    1. Receive ``split`` (SplitManifest), ``algorithm`` (str), and
       ``hyperparameters`` (Mapping | None) via process().
    2. Validate algorithm is non-empty and hyperparameters, if given, is a Mapping.
    3. Derive a deterministic model_id from SHA-256(algorithm + hyperparameters + split metadata).
    4. Return a ModelManifest reference.

Math:
    model_id = "<algorithm>:" + sha256(algorithm || hyperparameters || train_split_metadata)[0:16]

References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_ml.types.model_manifest import ModelManifest
from pirn_ml.types.split_manifest import SplitManifest


class Trainer(Knot):
    """Emit a :class:`ModelManifest` reference for a configured algorithm."""

    def __init__(
        self,
        *,
        split: Knot,
        algorithm: Knot | str,
        hyperparameters: Knot | Mapping[str, Any] | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            split=split,
            algorithm=algorithm,
            hyperparameters=hyperparameters,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        split: SplitManifest,
        algorithm: str,
        hyperparameters: Mapping[str, Any] | None = None,
        **_: Any,
    ) -> ModelManifest:
        """Derive a deterministic model_id from the split metadata and return a ModelManifest reference for the configured algorithm.

        Args:
            split: SplitManifest whose train partition metadata seeds the model_id
                hash and populates feature_names and target_name.
            algorithm: Non-empty algorithm name string.
            hyperparameters: Optional mapping of hyperparameter name to value.

        Returns:
            ModelManifest reference with a deterministic model_id derived from
            the algorithm, hyperparameters, and train-split metadata.

        Raises:
            ValueError: If algorithm is empty.
            TypeError: If hyperparameters is not a Mapping when provided.
        """
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError("Trainer: algorithm must be a non-empty string")
        if hyperparameters is not None and not isinstance(hyperparameters, Mapping):
            raise TypeError("Trainer: hyperparameters must be a Mapping[str, Any]")
        frozen_hp = MappingProxyType(dict(hyperparameters) if hyperparameters is not None else {})
        model_id = self._derive_model_id(split, algorithm, frozen_hp)
        return ModelManifest(
            model_id=model_id,
            algorithm=algorithm,
            hyperparameters=frozen_hp,
            feature_names=split.train.feature_names,
            target_name=split.train.target_name,
            created_at=datetime.now(UTC),
        )

    def _derive_model_id(
        self, split: SplitManifest, algorithm: str, hyperparameters: Mapping[str, Any]
    ) -> str:
        payload = json.dumps(
            {
                "algorithm": algorithm,
                "hyperparameters": dict(hyperparameters),
                "train_name": split.train.name,
                "train_row_count": split.train.row_count,
                "feature_names": list(split.train.feature_names),
                "target_name": split.train.target_name,
            },
            sort_keys=True,
            default=str,
        )
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return f"{algorithm}:{digest[:16]}"
