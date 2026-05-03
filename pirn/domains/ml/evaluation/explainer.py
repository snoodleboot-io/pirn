"""``Explainer`` — SHAP / permutation feature importance over a model + split.

The orchestration-layer base returns a deterministic mapping derived
from a hash of (``model_id``, feature, method, dataset name). Concrete
subclasses override :meth:`process` to compute real importances via
SHAP or scikit-learn's permutation importance.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, ClassVar, Mapping

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.trained_model import TrainedModel


class Explainer(Knot):
    """Per-feature importance estimator over a (model, split) pair."""

    valid_methods: ClassVar[frozenset[str]] = frozenset(
        {"permutation", "shap", "linear"}
    )

    def __init__(
        self,
        *,
        model: Knot,
        split: Knot,
        method: str = "permutation",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if method not in self.valid_methods:
            raise ValueError(
                f"Explainer: method must be one of {sorted(self.valid_methods)}"
            )
        self._method = method
        super().__init__(model=model, split=split, _config=_config, **kwargs)

    @property
    def method(self) -> str:
        return self._method

    async def process(
        self, model: TrainedModel, split: DataSplit, **_: Any
    ) -> Mapping[str, float]:
        """Compute feature importances for each model feature using the configured method and return a feature-to-importance mapping.

        Args:
            model: TrainedModel reference whose feature list drives the explanation.
            split: DataSplit whose test partition is used for importance scoring.

        Returns:
            Mapping of feature name to importance score in [0, 1).
        """
        return {
            feature: self._importance(model, split, feature)
            for feature in model.feature_names
        }

    def _importance(
        self, model: TrainedModel, split: DataSplit, feature: str
    ) -> float:
        payload = json.dumps(
            {
                "model_id": model.model_id,
                "method": self._method,
                "test_name": split.test.name,
                "feature": feature,
            },
            sort_keys=True,
            default=str,
        )
        digest = hashlib.sha256(payload.encode("utf-8")).digest()
        return int.from_bytes(digest[:8], "big") / float(2**64)
