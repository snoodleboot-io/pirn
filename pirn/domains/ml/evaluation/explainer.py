"""``Explainer`` — SHAP / permutation feature importance over a model + split.

The orchestration-layer base returns a deterministic mapping derived
from a hash of (``model_id``, feature, method, dataset name). Concrete
subclasses override :meth:`process` to compute real importances via
SHAP or scikit-learn's permutation importance.

Algorithm:
    1. Receive ``model`` (TrainedModel), ``split`` (DataSplit), and ``method`` (str) via process().
    2. Validate method against valid_methods.
    3. For each feature in model.feature_names, compute a deterministic importance score.
    4. Return a mapping of feature name to score.

Math:
    importance[feature] = sha256(model_id || method || test_name || feature)[0:8] as uint64 / 2^64

References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.trained_model import TrainedModel


class Explainer(Knot):
    """Per-feature importance estimator over a (model, split) pair."""

    valid_methods: ClassVar[frozenset[str]] = frozenset({"permutation", "shap", "linear"})

    def __init__(
        self,
        *,
        model: Knot,
        split: Knot,
        method: Knot | str = "permutation",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(model=model, split=split, method=method, _config=_config, **kwargs)

    async def process(
        self, model: TrainedModel, split: DataSplit, method: str = "permutation", **_: Any
    ) -> Mapping[str, float]:
        """Compute feature importances for each model feature using the configured method and return a feature-to-importance mapping.

        Args:
            model: TrainedModel reference whose feature list drives the explanation.
            split: DataSplit whose test partition is used for importance scoring.
            method: Importance method; must be one of ``valid_methods``.

        Returns:
            Mapping of feature name to importance score in [0, 1).

        Raises:
            ValueError: If method is not in valid_methods.
        """
        if method not in self.valid_methods:
            raise ValueError(f"Explainer: method must be one of {sorted(self.valid_methods)}")
        return {
            feature: self._importance(model, split, feature, method)
            for feature in model.feature_names
        }

    def _importance(
        self, model: TrainedModel, split: DataSplit, feature: str, method: str
    ) -> float:
        payload = json.dumps(
            {
                "model_id": model.model_id,
                "method": method,
                "test_name": split.test.name,
                "feature": feature,
            },
            sort_keys=True,
            default=str,
        )
        digest = hashlib.sha256(payload.encode("utf-8")).digest()
        return int.from_bytes(digest[:8], "big") / float(2**64)
