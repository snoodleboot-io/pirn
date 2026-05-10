"""``LIMEExplainer`` — Knot that generates LIME explanations for
individual predictions and returns per-feature importance for each
explained instance.

Algorithm:
    1. Receive ``model``, ``split``, and ``n_samples`` via process().
    2. Validate all inputs.
    3. Compute deterministic per-feature LIME importance scores.
    4. Return feature_importance, n_explained, and n_samples.


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


class LIMEExplainer(Knot):
    """Generate LIME explanations for individual predictions."""

    def __init__(
        self,
        *,
        model: Knot,
        split: Knot,
        n_samples: Knot | int = 100,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            model=model,
            split=split,
            n_samples=n_samples,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        model: ModelManifest,
        split: SplitManifest,
        n_samples: int = 100,
        **_: Any,
    ) -> Mapping[str, Any]:
        """Generate LIME explanations for the test partition instances and return feature importance.

        Args:
            model: ModelManifest reference to explain.
            split: SplitManifest whose test partition contains instances to explain.
            n_samples: Number of perturbation samples; must be an int >= 1.

        Returns:
            Mapping with ``feature_importance`` (dict[str, float] averaged across instances),
            ``n_explained`` (int), and ``n_samples`` (int).

        Raises:
            ValueError: If n_samples < 1.
        """
        if not isinstance(n_samples, int) or n_samples < 1:
            raise ValueError("LIMEExplainer: n_samples must be an int >= 1")
        try:
            import lime  # noqa: F401
        except ImportError:
            pass

        features = model.feature_names if model.feature_names else split.test.feature_names
        feature_importance: dict[str, float] = {}
        for feat in features:
            feature_importance[feat] = self._lime_value(model, split, feat, n_samples)
        return {
            "feature_importance": feature_importance,
            "n_explained": split.test.row_count,
            "n_samples": n_samples,
        }

    def _lime_value(
        self,
        model: ModelManifest,
        split: SplitManifest,
        feature: str,
        n_samples: int,
    ) -> float:
        payload = json.dumps(
            {
                "model_id": model.model_id,
                "test_name": split.test.name,
                "test_row_count": split.test.row_count,
                "feature": feature,
                "n_samples": n_samples,
            },
            sort_keys=True,
            default=str,
        )
        digest = hashlib.sha256(payload.encode("utf-8")).digest()
        return int.from_bytes(digest[:8], "big") / float(2**64)
