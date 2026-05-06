"""``Predictor`` — load a model id from the lineage store + object store
and emit predictions for a feature set.

The base implementation deterministically derives one prediction per
input row from the model id + features payload. Concrete subclasses
override :meth:`process` to deserialise the artifact and run real
inference.

Algorithm:
    1. Receive ``model_id`` (str), ``features`` (iterable of row dicts),
       ``lineage`` (LineageStore), and ``store`` (ObjectStore) via process().
    2. Validate that model_id is a non-empty string.
    3. Touch the lineage store to fail loudly on misconfiguration.
    4. For each feature row, derive a deterministic float score from
       SHA-256(model_id + row).
    5. Return the list of predictions.

Math:
    prediction[i] = sha256_bytes(model_id || row_i)[0:8] as uint64 / 2^64

References:
    N/A — pirn-native implementation.
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
        lineage: Knot | LineageStore,
        store: Knot | ObjectStore,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            model_id=model_id,
            features=features,
            lineage=lineage,
            store=store,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        model_id: str,
        features: Iterable[Mapping[str, Any]],
        lineage: LineageStore,
        store: ObjectStore = None,
        **_: Any,
    ) -> list[Any]:
        """Load the model from the registry and score each feature row, returning a list of predictions.

        Args:
            model_id: Non-empty string identifying the registered model.
            features: Iterable of feature row dicts to score.
            lineage: LineageStore used to fetch lineage for the model.
            store: ObjectStore (reserved for concrete subclasses that load artifacts).

        Returns:
            List of float predictions, one per input feature row.

        Raises:
            ValueError: If model_id resolves to an empty string.
        """
        if not isinstance(model_id, str) or not model_id:
            raise ValueError(
                "Predictor: model_id must resolve to a non-empty string"
            )
        # Touch the lineage store so misconfigured connectors fail loudly at
        # run time. The fetch results aren't required for deterministic scoring.
        await lineage.fetch_lineage(model_id)
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
