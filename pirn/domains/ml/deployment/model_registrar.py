"""``ModelRegistrar`` — write the serialised model + metadata to a
:class:`LineageStore` and an :class:`ObjectStore`.

Algorithm:
    1. Receive ``serialized`` (bytes), ``model`` (ModelManifest), ``lineage``
       (LineageStore), and ``store`` (ObjectStore) via process().
    2. Validate types for serialized and model.
    3. Derive the object store key as ``models/<model_id>.bin``.
    4. Write the serialised bytes to the object store under that key.
    5. Log a ``model_registered`` lineage event with model metadata.
    6. Return the model_id string.


References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.object_store import ObjectStore
from pirn.domains.ml.lineage_store import LineageStore
from pirn.domains.ml.types.model_manifest import ModelManifest


class ModelRegistrar(Knot):
    """Persist serialised model bytes + metadata."""

    def __init__(
        self,
        *,
        serialized: Knot,
        model: Knot,
        lineage: Knot | LineageStore,
        store: Knot | ObjectStore,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            serialized=serialized,
            model=model,
            lineage=lineage,
            store=store,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        serialized: bytes,
        model: ModelManifest,
        lineage: LineageStore,
        store: ObjectStore | None = None,
        **_: Any,
    ) -> str:
        """Write model bytes to the object store, log a lineage event, and return the model_id.

        Args:
            serialized: Serialised model bytes to store.
            model: ModelManifest reference providing the model_id and metadata.
            lineage: LineageStore used to log the registration event.
            store: ObjectStore where the serialised bytes are persisted.

        Returns:
            The model_id string from the ModelManifest.

        Raises:
            TypeError: If serialized is not bytes or model is not a ModelManifest.
        """
        if not isinstance(serialized, (bytes, bytearray)):
            raise TypeError("ModelRegistrar: serialized must resolve to bytes")
        if not isinstance(model, ModelManifest):
            raise TypeError("ModelRegistrar: model must resolve to a ModelManifest")
        if store is None:
            raise TypeError("ModelRegistrar: store must be an ObjectStore")
        key = f"models/{model.model_id}.bin"
        await store.put(key, bytes(serialized))
        await lineage.log_event(
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
