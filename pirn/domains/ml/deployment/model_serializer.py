"""``ModelSerializer`` — serialise a :class:`TrainedModel` reference to bytes.

The default implementation emits a JSON payload of the model's metadata
fields. Real subclasses (joblib / pickle / ONNX) override
:meth:`process` to serialise the actual fitted artifact.
"""

from __future__ import annotations

import json
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.types.trained_model import TrainedModel


class ModelSerializer(Knot):
    """Serialise a :class:`TrainedModel` reference to ``bytes``."""

    valid_formats: ClassVar[frozenset[str]] = frozenset(
        {"joblib", "pickle", "onnx", "json", "xgboost-json", "pytorch"}
    )

    def __init__(
        self,
        *,
        model: Knot,
        format: str = "joblib",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if format not in self.valid_formats:
            raise ValueError(
                f"ModelSerializer: format must be one of "
                f"{sorted(self.valid_formats)}"
            )
        self._format = format
        super().__init__(model=model, _config=_config, **kwargs)

    @property
    def format(self) -> str:
        return self._format

    async def process(self, model: TrainedModel, **_: Any) -> bytes:
        """Serialise the TrainedModel metadata to bytes in the configured format and return them.

        Args:
            model: TrainedModel reference whose metadata is serialised.

        Returns:
            UTF-8 encoded JSON bytes containing the model metadata payload.
        """
        payload = {
            "format": self._format,
            "model_id": model.model_id,
            "algorithm": model.algorithm,
            "hyperparameters": dict(model.hyperparameters),
            "feature_names": list(model.feature_names),
            "target_name": model.target_name,
            "created_at": model.created_at.isoformat(),
        }
        return json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
