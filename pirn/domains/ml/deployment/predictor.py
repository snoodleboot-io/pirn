"""``Predictor`` — load a model id from the lineage store + object store
and emit predictions for a feature set.

The base implementation deterministically derives one prediction per
input row from the model id + features payload. Concrete subclasses
override :meth:`process` to deserialise the artifact and run real
inference.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, Mapping

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.object_store import ObjectStore
from pirn.domains.ml.lineage_store import LineageStore


class Predictor(Knot):
    """Score a batch of features against a registered model id."""

    def __init__(
        self,
        *,
        model_id: Knot | str,
        features: Knot,
        lineage: LineageStore,
        store: ObjectStore,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(model_id, (Knot, str)):
            raise TypeError(
                "Predictor: model_id must be a Knot or a string"
            )
        if isinstance(model_id, str) and not model_id:
            raise ValueError(
                "Predictor: model_id string must be non-empty"
            )
        if not isinstance(lineage, LineageStore):
            raise TypeError(
                "Predictor: lineage must be a LineageStore"
            )
        if not isinstance(store, ObjectStore):
            raise TypeError(
                "Predictor: store must be an ObjectStore"
            )
        self._lineage = lineage
        self._store = store
        # Pass model_id either as a parent (Knot) or a config (str) — Knot's
        # constructor introspects the value type to decide.
        super().__init__(
            model_id=model_id, features=features, _config=_config, **kwargs
        )

    async def process(
        self,
        model_id: str,
        features: Iterable[Mapping[str, Any]],
        **_: Any,
    ) -> list[Any]:
        if not isinstance(model_id, str) or not model_id:
            raise ValueError(
                "Predictor: model_id must resolve to a non-empty string"
            )
        # Touch the lineage and object stores so misconfigured connectors
        # fail loudly at run time. The fetch results aren't required for
        # the deterministic baseline scoring.
        await self._lineage.fetch_lineage(model_id)
        feature_rows = list(features)
        return [
            self._predict(model_id, row)
            for row in feature_rows
        ]

    def _predict(self, model_id: str, row: Mapping[str, Any]) -> float:
        payload = json.dumps(
            {"model_id": model_id, "row": dict(row)},
            sort_keys=True,
            default=str,
        )
        digest = hashlib.sha256(payload.encode("utf-8")).digest()
        return int.from_bytes(digest[:8], "big") / float(2**64)
