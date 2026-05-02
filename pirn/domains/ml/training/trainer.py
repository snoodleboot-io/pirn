"""``Trainer`` — train one model on a :class:`DataSplit.train` slice.

At this orchestration layer the knot does not actually fit a model; it
emits a deterministic :class:`TrainedModel` reference whose ``model_id``
hashes the algorithm + hyperparameters + train-split metadata. Concrete
subclasses (e.g. ``SklearnTrainer``) override :meth:`process` to perform
the actual fit using the upstream data and return a real artifact id.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Mapping

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.trained_model import TrainedModel


class Trainer(Knot):
    """Emit a :class:`TrainedModel` reference for a configured algorithm."""

    def __init__(
        self,
        *,
        split: Knot,
        algorithm: str,
        hyperparameters: Mapping[str, Any] | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError(
                "Trainer: algorithm must be a non-empty string"
            )
        if hyperparameters is not None and not isinstance(
            hyperparameters, Mapping
        ):
            raise TypeError(
                "Trainer: hyperparameters must be a Mapping[str, Any]"
            )
        frozen_hp = MappingProxyType(
            dict(hyperparameters) if hyperparameters is not None else {}
        )
        self._algorithm = algorithm
        self._hyperparameters = frozen_hp
        super().__init__(split=split, _config=_config, **kwargs)

    @property
    def algorithm(self) -> str:
        return self._algorithm

    @property
    def hyperparameters(self) -> Mapping[str, Any]:
        return self._hyperparameters

    async def process(self, split: DataSplit, **_: Any) -> TrainedModel:
        model_id = self._derive_model_id(split)
        return TrainedModel(
            model_id=model_id,
            algorithm=self._algorithm,
            hyperparameters=self._hyperparameters,
            feature_names=split.train.feature_names,
            target_name=split.train.target_name,
            created_at=datetime.now(timezone.utc),
        )

    def _derive_model_id(self, split: DataSplit) -> str:
        payload = json.dumps(
            {
                "algorithm": self._algorithm,
                "hyperparameters": dict(self._hyperparameters),
                "train_name": split.train.name,
                "train_row_count": split.train.row_count,
                "feature_names": list(split.train.feature_names),
                "target_name": split.train.target_name,
            },
            sort_keys=True,
            default=str,
        )
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return f"{self._algorithm}:{digest[:16]}"
