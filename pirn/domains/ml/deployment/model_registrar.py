"""``ModelRegistrar`` — write the serialised model + metadata to a
:class:`LineageStore` and an :class:`ObjectStore`.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.object_store import ObjectStore
from pirn.domains.ml.lineage_store import LineageStore
from pirn.domains.ml.types.trained_model import TrainedModel


class ModelRegistrar(Knot):
    """Persist serialised model bytes + metadata."""

    def __init__(
        self,
        *,
        serialized: Knot,
        model: Knot,
        lineage: LineageStore,
        store: ObjectStore,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(lineage, LineageStore):
            raise TypeError(
                "ModelRegistrar: lineage must be a LineageStore"
            )
        if not isinstance(store, ObjectStore):
            raise TypeError(
                "ModelRegistrar: store must be an ObjectStore"
            )
        self._lineage = lineage
        self._store = store
        super().__init__(
            serialized=serialized, model=model, _config=_config, **kwargs
        )

    async def process(
        self, serialized: bytes, model: TrainedModel, **_: Any
    ) -> str:
        if not isinstance(serialized, (bytes, bytearray)):
            raise TypeError(
                "ModelRegistrar: serialized must resolve to bytes"
            )
        if not isinstance(model, TrainedModel):
            raise TypeError(
                "ModelRegistrar: model must resolve to a TrainedModel"
            )
        key = f"models/{model.model_id}.bin"
        await self._store.put(key, bytes(serialized))
        await self._lineage.log_event(
            "model_registered",
            {
                "model_id": model.model_id,
                "algorithm": model.algorithm,
                "object_key": key,
                "feature_names": list(model.feature_names),
                "target_name": model.target_name,
            },
        )
        return model.model_id
