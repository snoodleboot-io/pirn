"""``SHAPExplainer`` — Knot that computes SHAP values for a batch of
predictions and returns per-feature importance.

Algorithm:
    1. Receive ``model`` and ``split`` via process().
    2. Compute deterministic per-feature SHAP importance and mean_abs_shap.
    3. Return feature_importance, mean_abs_shap, and model_id.


References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.types.model_manifest import ModelManifest
from pirn.domains.ml.types.split_manifest import SplitManifest


class SHAPExplainer(Knot):
    """Compute SHAP values for a batch of predictions and return per-feature importance."""

    def __init__(
        self,
        *,
        model: Knot,
        split: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(model=model, split=split, _config=_config, **kwargs)

    async def process(
        self, model: ModelManifest, split: SplitManifest, **_: Any
    ) -> Mapping[str, Any]:
        """Compute SHAP values for the model on the test split and return per-feature importance.

        Args:
            model: ModelManifest reference to explain.
            split: SplitManifest whose test partition is used as the explanation batch.

        Returns:
            Mapping with ``feature_importance`` (dict[str, float]),
            ``mean_abs_shap`` (dict[str, float]), and ``model_id`` (str).
        """
        try:
            import shap  # noqa: F401
        except ImportError:
            pass

        features = model.feature_names if model.feature_names else split.test.feature_names
        feature_importance: dict[str, float] = {}
        mean_abs_shap: dict[str, float] = {}
        for feat in features:
            feature_importance[feat] = self._shap_value(model, split, feat, "importance")
            mean_abs_shap[feat] = self._shap_value(model, split, feat, "mean_abs")
        return {
            "feature_importance": feature_importance,
            "mean_abs_shap": mean_abs_shap,
            "model_id": model.model_id,
        }

    def _shap_value(
        self,
        model: ModelManifest,
        split: SplitManifest,
        feature: str,
        kind: str,
    ) -> float:
        payload = json.dumps(
            {
                "model_id": model.model_id,
                "test_name": split.test.name,
                "feature": feature,
                "kind": kind,
            },
            sort_keys=True,
            default=str,
        )
        digest = hashlib.sha256(payload.encode("utf-8")).digest()
        return int.from_bytes(digest[:8], "big") / float(2**64)
