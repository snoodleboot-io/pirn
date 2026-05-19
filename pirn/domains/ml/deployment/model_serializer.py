"""``ModelSerializer`` — serialise a :class:`ModelManifest` reference to bytes.

The default implementation emits a JSON payload of the model's metadata
fields. Real subclasses (joblib / pickle / ONNX) override
:meth:`process` to serialise the actual fitted artifact.

Algorithm:
    1. Receive ``model`` (ModelManifest) and ``format`` (str) via process().
    2. Validate format against the known set of valid formats.
    3. Build a JSON-serialisable payload from model metadata fields.
    4. Encode the payload to UTF-8 bytes and return.


References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

import json
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.types.model_manifest import ModelManifest


class ModelSerializer(Knot):
    """Serialise a :class:`ModelManifest` reference to ``bytes``."""

    valid_formats: ClassVar[frozenset[str]] = frozenset(
        {"joblib", "pickle", "onnx", "json", "xgboost-json", "pytorch"}
    )

    def __init__(
        self,
        *,
        model: Knot,
        format: Knot | str = "joblib",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(model=model, format=format, _config=_config, **kwargs)

    async def process(self, model: ModelManifest, format: str = "joblib", **_: Any) -> bytes:
        """Serialise the ModelManifest metadata to bytes in the configured format and return them.

        Args:
            model: ModelManifest reference whose metadata is serialised.
            format: Serialisation format; must be one of ``valid_formats``.

        Returns:
            UTF-8 encoded JSON bytes containing the model metadata payload.

        Raises:
            ValueError: If format is not a known serialisation format.
        """
        if format not in self.valid_formats:
            raise ValueError(f"ModelSerializer: format must be one of {sorted(self.valid_formats)}")
        payload = {
            "format": format,
            "model_id": model.model_id,
            "algorithm": model.algorithm,
            "hyperparameters": dict(model.hyperparameters),
            "feature_names": list(model.feature_names),
            "target_name": model.target_name,
            "created_at": model.created_at.isoformat(),
        }
        return json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
