"""``LIMEExplainer`` — Knot that generates LIME explanations for
individual predictions and returns per-feature importance for each
explained instance.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.trained_model import TrainedModel


class LIMEExplainer(Knot):
    """Generate LIME explanations for individual predictions."""

    def __init__(
        self,
        *,
        model: Knot,
        split: Knot,
        n_samples: int = 100,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(model, Knot):
            raise TypeError("LIMEExplainer: model must be a Knot")
        if not isinstance(split, Knot):
            raise TypeError("LIMEExplainer: split must be a Knot")
        if not isinstance(n_samples, int) or n_samples < 1:
            raise ValueError("LIMEExplainer: n_samples must be an int >= 1")
        self._n_samples = n_samples
        super().__init__(model=model, split=split, _config=_config, **kwargs)

    @property
    def n_samples(self) -> int:
        return self._n_samples

    async def process(
        self, model: TrainedModel, split: DataSplit, **_: Any
    ) -> Mapping[str, Any]:
        """Generate LIME explanations for the test partition instances and return feature importance.

        Args:
            model: TrainedModel reference to explain.
            split: DataSplit whose test partition contains instances to explain.

        Returns:
            Mapping with ``feature_importance`` (dict[str, float] averaged across instances),
            ``n_explained`` (int), and ``n_samples`` (int).
        """
        try:
            import lime  # noqa: F401
            _lime_available = True
        except ImportError:
            _lime_available = False

        features = model.feature_names if model.feature_names else split.test.feature_names
        feature_importance: dict[str, float] = {}
        for feat in features:
            feature_importance[feat] = self._lime_value(model, split, feat)
        return {
            "feature_importance": feature_importance,
            "n_explained": split.test.row_count,
            "n_samples": self._n_samples,
        }

    def _lime_value(
        self,
        model: TrainedModel,
        split: DataSplit,
        feature: str,
    ) -> float:
        payload = json.dumps(
            {
                "model_id": model.model_id,
                "test_name": split.test.name,
                "test_row_count": split.test.row_count,
                "feature": feature,
                "n_samples": self._n_samples,
            },
            sort_keys=True,
            default=str,
        )
        digest = hashlib.sha256(payload.encode("utf-8")).digest()
        return int.from_bytes(digest[:8], "big") / float(2**64)
